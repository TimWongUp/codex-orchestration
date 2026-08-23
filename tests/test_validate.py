from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast


class ExecutableLoader(Protocol):
    def exec_module(self, module: ModuleType) -> None: ...


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate.py"
SPEC = importlib.util.spec_from_file_location("source_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
cast(ExecutableLoader, SPEC.loader).exec_module(VALIDATOR)


class SourceValidationTest(unittest.TestCase):
    def copy_runtime(self, temporary_path: Path) -> tuple[Path, Path]:
        codex_home = temporary_path / "codex-home"
        skills_root = temporary_path / "skills"
        for name, source in VALIDATOR.BUNDLED_SKILLS.items():
            target = skills_root / name
            if name == "codex-orchestration":
                target.mkdir(parents=True)
                shutil.copy2(source / "SKILL.md", target / "SKILL.md")
                shutil.copytree(source / "references", target / "references")
            else:
                shutil.copytree(source, target)

        agents_target = codex_home / "agents"
        agents_target.mkdir(parents=True)
        for source in (ROOT / "agents").glob("*.toml"):
            shutil.copy2(source, agents_target / source.name)
        return codex_home, skills_root

    def test_source_contract(self) -> None:
        self.assertEqual(VALIDATOR.validate_source(), [])

    def test_routing_example_schema_rejects_unknown_roles_and_invalid_values(self) -> None:
        source = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")
        self.assertEqual(VALIDATOR.routing_example_failures(source), [])

        unknown_role = source.replace('roles = ["ROLE_NAME"]', 'roles = ["unknown-role"]')
        self.assertIn(
            "routing override 1 has invalid roles",
            VALIDATOR.routing_example_failures(unknown_role),
        )

        invalid_value = source.replace('model = "MODEL_ID_OVERRIDE"', "model = [")
        self.assertTrue(
            any(
                "invalid value" in failure
                for failure in VALIDATOR.routing_example_failures(invalid_value)
            )
        )

        concrete_model = source.replace('model = "MODEL_ID_OVERRIDE"', 'model = "gpt-example"')
        self.assertIn(
            "routing example contains a non-placeholder model",
            VALIDATOR.routing_example_failures(concrete_model),
        )

    def test_source_helpers_reject_model_pins_and_public_model_routes(self) -> None:
        profile = 'name = "reviewer"\nmodel = "provider/model"\n'
        self.assertEqual(VALIDATOR.pinned_model_keys(profile), {"model"})
        self.assertTrue(
            any(
                "machine-specific model route" in failure
                for failure in VALIDATOR.public_pattern_failures("sample.md", "xai/" + "grok")
            )
        )

    def test_task_package_language_schema_accepts_supported_values(self) -> None:
        source = (ROOT / "examples" / "preferences.toml").read_text(encoding="utf-8")
        self.assertEqual(
            VALIDATOR.preferences_failures(source, allow_placeholder=True),
            [],
        )
        for language in ("en", "zh-CN"):
            with self.subTest(language=language):
                selected = source.replace('"LANGUAGE"', f'"{language}"')
                self.assertEqual(VALIDATOR.preferences_failures(selected), [])

        unsupported = source.replace('"LANGUAGE"', '"fr"')
        self.assertIn(
            "preferences task_package_language is invalid",
            VALIDATOR.preferences_failures(unsupported),
        )

        extra_field = source + 'unexpected = "value"\n'
        self.assertIn(
            "preferences fields are invalid",
            VALIDATOR.preferences_failures(extra_field, allow_placeholder=True),
        )

        boolean_version = source.replace("schema_version = 1", "schema_version = True")
        self.assertIn(
            "preferences schema_version is invalid",
            VALIDATOR.preferences_failures(boolean_version, allow_placeholder=True),
        )

        for invalid_toml in (
            source.replace('"LANGUAGE"', r'"\x4cANGUAGE"'),
            source.replace('"LANGUAGE"', '"LANGUAGE" ""'),
        ):
            with self.subTest(invalid_toml=invalid_toml):
                self.assertTrue(
                    any(
                        "invalid value" in failure
                        for failure in VALIDATOR.preferences_failures(
                            invalid_toml, allow_placeholder=True
                        )
                    )
                )

    def test_hook_outputs_match_contract(self) -> None:
        def run_hook(script: str, payload: str = "") -> dict[str, str]:
            result = subprocess.run(
                [sys.executable, str(ROOT / "hooks" / script)],
                input=payload,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return cast(dict[str, str], json.loads(result.stdout)["hookSpecificOutput"])

        route = run_hook("orchestration_route.py")
        self.assertEqual(route["hookEventName"], "UserPromptSubmit")
        self.assertIn("Wait before decisions, writes, or final answers", route["additionalContext"])
        self.assertIn("independent, non-overlapping work", route["additionalContext"])
        self.assertIn("If a wait times out", route["additionalContext"])
        self.assertIn("USER_REQUESTED_INTERRUPT:", route["additionalContext"])
        self.assertIn("ORCHESTRATOR_CORRECTION:", route["additionalContext"])
        self.assertIn("terminal status", route["additionalContext"])

        for payload, expected, forbidden in (
            ('{"agent_type":"worker"}', "complete canonical", "You are read-only"),
            ('{"agent_type":"explorer"}', "read-only", "You are a writable worker"),
            ('{"agentType":"explorer"}', "read-only", "You are a writable worker"),
            ('{"agent_type":"unknown"}', "read-only", "You are a writable worker"),
            ("[]", "read-only", "You are a writable worker"),
        ):
            with self.subTest(payload=payload):
                scope = run_hook("subagent_scope.py", payload)
                self.assertEqual(scope["hookEventName"], "SubagentStart")
                self.assertIn(expected, scope["additionalContext"])
                self.assertIn("HIGH PRIORITY DERIVED-AGENT IDENTITY", scope["additionalContext"])
                self.assertIn(
                    "Do not load or execute the codex-orchestration Skill",
                    scope["additionalContext"],
                )
                self.assertIn("panel member", scope["additionalContext"])
                self.assertNotIn(forbidden, scope["additionalContext"])
                if "worker" not in payload:
                    self.assertNotIn("WRITE LEASE: granted", scope["additionalContext"])
                if "worker" in payload:
                    for field in VALIDATOR.WORKER_PACKAGE_FIELDS:
                        self.assertIn(field, scope["additionalContext"])

    def test_subagent_guard_controls_interrupt_only(self) -> None:
        def run_guard(payload: dict[str, object]) -> dict[str, object]:
            result = subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "subagent_guard.py")],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return cast(dict[str, object], json.loads(result.stdout))

        denied = run_guard(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "multi_agent_v1send_input",
                "tool_input": {"target": "agent-a", "interrupt": True, "message": "stop"},
            }
        )
        self.assertEqual(
            cast(dict[str, object], denied["hookSpecificOutput"])["permissionDecision"],
            "deny",
        )

        self.assertEqual(
            run_guard(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": False,
                        "message": "continue when ready",
                    },
                }
            ),
            {},
        )
        for carrier, text in (
            ("message", "USER_REQUESTED_INTERRUPT: stop"),
            ("items", "USER_REQUESTED_INTERRUPT: stop"),
            ("message", "ORCHESTRATOR_CORRECTION: wrong_role\nReturn to the assigned role."),
            ("items", "ORCHESTRATOR_CORRECTION: scope_drift\nReturn to scope."),
        ):
            with self.subTest(carrier=carrier, text=text):
                tool_input: dict[str, object] = {"target": "agent-a", "interrupt": True}
                if carrier == "message":
                    tool_input["message"] = text
                else:
                    tool_input["items"] = [{"type": "text", "text": text}]
                self.assertEqual(
                    run_guard(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "send_input",
                            "tool_input": tool_input,
                        }
                    ),
                    {},
                )

        for reason in (
            "wrong_model",
            "wrong_role",
            "descendant_orchestration",
            "scope_drift",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(
                    run_guard(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "send_input",
                            "tool_input": {
                                "target": "agent-a",
                                "interrupt": True,
                                "message": f"ORCHESTRATOR_CORRECTION: {reason}\nCorrect now.",
                            },
                        }
                    ),
                    {},
                )

        invalid_inputs: tuple[dict[str, object], ...] = (
            {"interrupt": True, "items": [{"type": "text", "text": "replace reviewer"}]},
            {"interrupt": "true", "message": "USER_REQUESTED_INTERRUPT: stop"},
            {"interrupt": True, "message": "ORCHESTRATOR_CORRECTION: stop"},
            {"interrupt": True, "message": "ORCHESTRATOR_CORRECTION: timeout"},
            {"interrupt": True, "message": "ORCHESTRATOR_CORRECTION: too_slow"},
            {"interrupt": True, "message": "ORCHESTRATOR_CORRECTION: unknown"},
        )
        for tool_input in invalid_inputs:
            with self.subTest(tool_input=tool_input):
                denied_input = {"target": "agent-a", **tool_input}
                result = run_guard(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "send_input",
                        "tool_input": denied_input,
                    }
                )
                self.assertEqual(
                    cast(dict[str, object], result["hookSpecificOutput"])["permissionDecision"],
                    "deny",
                )

        for tool_name in ("close_agent", "wait_agent"):
            with self.subTest(tool_name=tool_name):
                self.assertEqual(
                    run_guard(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": tool_name,
                            "tool_input": {"target": "agent-a"},
                        }
                    ),
                    {},
                )

    def test_runtime_validation_accepts_copied_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

    def test_runtime_validation_checks_saved_task_package_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            preferences = codex_home / "codex-orchestration" / "preferences.toml"
            preferences.parent.mkdir()
            preferences.write_text(
                'schema_version = 1\ntask_package_language = "zh-CN"\n',
                encoding="utf-8",
            )
            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

            preferences.write_text(
                'schema_version = 1\ntask_package_language = "fr"\n',
                encoding="utf-8",
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("runtime preferences invalid" in failure for failure in failures))

    def test_runtime_validation_reports_missing_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            failures = VALIDATOR.validate_runtime(
                temporary_path / "codex-home", temporary_path / "skills"
            )

        self.assertTrue(any("runtime Skill missing" in failure for failure in failures))
        self.assertTrue(any("runtime Agent directory missing" in failure for failure in failures))

    def test_runtime_validation_reports_main_skill_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            (skills_root / "codex-orchestration" / "SKILL.md").write_text(
                "drift\n", encoding="utf-8"
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("runtime Skill file differs" in failure for failure in failures))

    def test_runtime_validation_rejects_method_skill_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            (skills_root / "prototype" / "SKILL.md").write_text(
                "---\nname: prototype\n---\n", encoding="utf-8"
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("prototype" in failure for failure in failures))

    def test_runtime_validation_rejects_linked_skill_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home, skills_root = self.copy_runtime(temporary_path)
            target = skills_root / "codex-orchestration"
            external = temporary_path / "external"
            shutil.move(target, external)
            try:
                target.symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("linked" in failure for failure in failures))

    def test_runtime_validation_rejects_linked_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home, skills_root = self.copy_runtime(temporary_path)
            linked_root = temporary_path / "linked-skills"
            try:
                linked_root.symlink_to(skills_root, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            failures = VALIDATOR.validate_runtime(codex_home, linked_root.absolute())

        self.assertTrue(any("linked path component" in failure for failure in failures))

    def test_runtime_validation_rejects_linked_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home, skills_root = self.copy_runtime(temporary_path)
            external = temporary_path / "external-codex-home"
            shutil.move(codex_home, external)
            try:
                codex_home.symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            failures = VALIDATOR.validate_runtime(codex_home.absolute(), skills_root)

        self.assertTrue(any("linked path component" in failure for failure in failures))

    def test_runtime_validation_ignores_unselected_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "orchestration_route.py").write_text("custom\n", encoding="utf-8")

            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

    def test_hook_validation_accepts_one_registration_per_event(self) -> None:
        for windows in (False, True):
            with (
                self.subTest(windows=windows),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                hooks: dict[str, list[dict[str, object]]] = {}
                for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                    shutil.copy2(ROOT / "hooks" / script, hooks_root / script)
                    command = VALIDATOR.expected_hook_command(hooks_root / script, windows=windows)
                    hook: dict[str, object] = {"type": "command", "command": command}
                    if windows:
                        hook["commandWindows"] = command
                    group: dict[str, object] = {"hooks": [hook]}
                    if matcher is not None:
                        group["matcher"] = matcher
                    hooks[event] = [group]
                hooks["SessionStart"] = [{"hooks": [{"type": "command", "command": "foreign"}]}]
                hooks["PreToolUse"].append(
                    {
                        "matcher": "bash$",
                        "hooks": [{"type": "command", "command": "foreign"}],
                    }
                )
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                self.assertEqual(VALIDATOR.validate_hooks(codex_home, windows=windows), [])

    def test_hook_validation_rejects_stale_managed_guard_registrations(self) -> None:
        for event, matcher in (
            ("PostToolUse", r"wait_agent$"),
            ("PreToolUse", r"close_agent$"),
            ("PreToolUse", r"send_input$|close_agent$"),
        ):
            with (
                self.subTest(event=event, matcher=matcher),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                hooks: dict[str, list[dict[str, object]]] = {}
                windows = VALIDATOR.os.name == "nt"
                for managed_event, script, managed_matcher in VALIDATOR.HOOK_REGISTRATIONS:
                    target = hooks_root / script
                    shutil.copy2(ROOT / "hooks" / script, target)
                    command = VALIDATOR.expected_hook_command(target, windows=windows)
                    hook: dict[str, object] = {"type": "command", "command": command}
                    if windows:
                        hook["commandWindows"] = command
                    group: dict[str, object] = {"hooks": [hook]}
                    if managed_matcher is not None:
                        group["matcher"] = managed_matcher
                    hooks[managed_event] = [group]

                guard_target = hooks_root / "subagent_guard.py"
                stale_command = VALIDATOR.expected_hook_command(guard_target, windows=windows)
                stale_hook: dict[str, object] = {
                    "type": "command",
                    "command": stale_command,
                }
                if windows:
                    stale_hook["commandWindows"] = stale_command
                hooks.setdefault(event, []).append({"matcher": matcher, "hooks": [stale_hook]})
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home, windows=windows)

            self.assertTrue(
                any("stale managed guard registration" in failure for failure in failures)
            )

    def test_guard_registration_only_covers_send_input(self) -> None:
        self.assertEqual(
            VALIDATOR.HOOK_REGISTRATIONS,
            (
                ("UserPromptSubmit", "orchestration_route.py", None),
                ("SubagentStart", "subagent_scope.py", None),
                ("PreToolUse", "subagent_guard.py", r"send_input$"),
            ),
        )

    def test_runtime_cli_validates_selected_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            hooks: dict[str, list[dict[str, object]]] = {}
            windows = VALIDATOR.os.name == "nt"
            for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                target = hooks_root / script
                shutil.copy2(ROOT / "hooks" / script, target)
                command = VALIDATOR.expected_hook_command(target, windows=windows)
                hook: dict[str, object] = {"type": "command", "command": command}
                if windows:
                    hook["commandWindows"] = command
                group: dict[str, object] = {"hooks": [hook]}
                if matcher is not None:
                    group["matcher"] = matcher
                hooks[event] = [group]
            (codex_home / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--runtime",
                    "--codex-home",
                    str(codex_home),
                    "--skills-root",
                    str(skills_root),
                    "--hooks",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: runtime skill and agents match source", result.stdout)

    def test_hook_validation_rejects_non_exact_commands(self) -> None:
        for command_kind in ("path-substring", "path-suffix", "extra-argument"):
            with (
                self.subTest(command_kind=command_kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                hooks: dict[str, list[dict[str, object]]] = {}
                windows = VALIDATOR.os.name == "nt"
                for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                    target = hooks_root / script
                    shutil.copy2(ROOT / "hooks" / script, target)
                    if command_kind == "path-substring":
                        command = f'echo "{target}"'
                    elif command_kind == "path-suffix":
                        command = VALIDATOR.expected_hook_command(
                            Path(f"{target}.disabled"), windows=windows
                        )
                    else:
                        command = (
                            f"{VALIDATOR.expected_hook_command(target, windows=windows)} extra"
                        )
                    hook: dict[str, object] = {"type": "command", "command": command}
                    if windows:
                        hook["commandWindows"] = command
                    group: dict[str, object] = {"hooks": [hook]}
                    if matcher is not None:
                        group["matcher"] = matcher
                    hooks[event] = [group]
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home)

            self.assertTrue(any("registration count is 0" in failure for failure in failures))

    def test_expected_hook_command_uses_windows_quoting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "hook scripts" / "guard.py"
            windows_command = VALIDATOR.expected_hook_command(target, windows=True)
            posix_command = VALIDATOR.expected_hook_command(target, windows=False)

        self.assertNotEqual(windows_command, posix_command)
        self.assertIn(f'"{target.absolute()}"', windows_command)
        self.assertIn(f"'{target.absolute()}'", posix_command)

    def test_hook_validation_rejects_missing_or_invalid_windows_fields(self) -> None:
        for invalid_field in (
            "missing-command",
            "invalid-command",
            "missing-commandWindows",
            "invalid-commandWindows",
        ):
            with (
                self.subTest(invalid_field=invalid_field),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                hooks: dict[str, list[dict[str, object]]] = {}
                for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                    target = hooks_root / script
                    shutil.copy2(ROOT / "hooks" / script, target)
                    hook: dict[str, object] = {
                        "type": "command",
                        "command": VALIDATOR.expected_hook_command(target, windows=True),
                        "commandWindows": VALIDATOR.expected_hook_command(target, windows=True),
                    }
                    if invalid_field == "missing-command":
                        del hook["command"]
                    elif invalid_field == "invalid-command":
                        hook["command"] = "invalid"
                    elif invalid_field == "missing-commandWindows":
                        del hook["commandWindows"]
                    else:
                        hook["commandWindows"] = "invalid"
                    group: dict[str, object] = {"hooks": [hook]}
                    if matcher is not None:
                        group["matcher"] = matcher
                    hooks[event] = [group]
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home, windows=True)

            self.assertTrue(any("registration count is 0" in failure for failure in failures))

    def test_hook_validation_rejects_guard_matcher_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            hooks: dict[str, list[dict[str, object]]] = {}
            windows = VALIDATOR.os.name == "nt"
            for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                target = hooks_root / script
                shutil.copy2(ROOT / "hooks" / script, target)
                command = VALIDATOR.expected_hook_command(target, windows=windows)
                hook: dict[str, object] = {"type": "command", "command": command}
                if windows:
                    hook["commandWindows"] = command
                group: dict[str, object] = {"hooks": [hook]}
                if matcher is not None:
                    group["matcher"] = "Agent" if event == "PreToolUse" else matcher
                hooks[event] = [group]
            (codex_home / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

            failures = VALIDATOR.validate_hooks(codex_home)

        self.assertTrue(any("PreToolUse" in failure for failure in failures))

    def test_hook_validation_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            for source in (ROOT / "hooks").glob("*.py"):
                shutil.copy2(source, hooks_root / source.name)
            (codex_home / "hooks.json").write_text("{invalid", encoding="utf-8")

            failures = VALIDATOR.validate_hooks(codex_home)

        self.assertTrue(any("hooks config invalid" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
