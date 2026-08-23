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
from unittest import mock


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

    def test_v2_tool_contract_is_explicit(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        route = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "orchestration_route.py")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(route.returncode, 0, route.stderr)
        context = cast(dict[str, object], json.loads(route.stdout)["hookSpecificOutput"])
        additional = cast(str, context["additionalContext"])
        for text in (
            'fork_turns="none"',
            "positive value",
            "partial history",
            "send_message",
            "followup_task",
            "wait_agent",
            "interrupt_agent",
            "list_agents",
            "caller's mailbox",
            "final notifications",
        ):
            with self.subTest(text=text):
                self.assertIn(text, skill)
                self.assertIn(text, additional)
        self.assertIn("Omitting `fork_turns`", skill)
        self.assertIn("Omitting fork_turns", additional)

    def test_routing_example_schema_rejects_service_placement_and_invalid_values(self) -> None:
        source = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")
        self.assertEqual(VALIDATOR.routing_example_failures(source), [])

        invalid_override_service = source.replace(
            'reasoning_effort = "REASONING_LEVEL"',
            'reasoning_effort = "REASONING_LEVEL"\nservice_tier = "SERVICE_TIER"',
            1,
        )
        self.assertTrue(
            any(
                "unknown fields" in failure
                for failure in VALIDATOR.routing_example_failures(invalid_override_service)
            )
        )

        invalid_role_service = source.replace(
            'model = "MODEL_ID_PRIMARY"',
            'model = "MODEL_ID_PRIMARY"\nservice_tier = "SERVICE_TIER"',
        )
        self.assertTrue(
            any(
                "unknown fields" in failure
                for failure in VALIDATOR.routing_example_failures(invalid_role_service)
            )
        )

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

    def test_source_helpers_reject_model_pins_and_public_model_routes(self) -> None:
        profile = (
            'name = "reviewer"\nmodel = "provider/model"\n'
            'model_reasoning_effort = "high"\nservice_tier = "priority"\n'
        )
        self.assertEqual(
            VALIDATOR.pinned_model_keys(profile),
            {"model", "model_reasoning_effort", "service_tier"},
        )
        self.assertTrue(
            any(
                "machine-specific model route" in failure
                for failure in VALIDATOR.public_pattern_failures("sample.md", "xai/" + "grok")
            )
        )

    def test_task_package_language_schema_accepts_supported_values(self) -> None:
        source = (ROOT / "examples" / "preferences.toml").read_text(encoding="utf-8")
        self.assertEqual(VALIDATOR.preferences_failures(source, allow_placeholder=True), [])
        for language in ("en", "zh-CN"):
            with self.subTest(language=language):
                selected = source.replace('"LANGUAGE"', f'"{language}"')
                self.assertEqual(VALIDATOR.preferences_failures(selected), [])

        unsupported = source.replace('"LANGUAGE"', '"fr"')
        self.assertIn(
            "preferences task_package_language is invalid",
            VALIDATOR.preferences_failures(unsupported),
        )

    def test_scope_hook_exposes_lease_only_for_writers(self) -> None:
        def run_scope(payload: str) -> dict[str, object]:
            result = subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "subagent_scope.py")],
                input=payload,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return cast(dict[str, object], json.loads(result.stdout)["hookSpecificOutput"])

        worker = cast(str, run_scope('{"agent_type":"worker"}')["additionalContext"])
        reader = cast(str, run_scope('{"agent_type":"explorer"}')["additionalContext"])
        self.assertIn("WRITE LEASE: granted", worker)
        self.assertIn("GOAL", worker)
        self.assertIn("You are read-only", reader)
        self.assertNotIn("WRITE LEASE: granted", reader)

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

    def test_runtime_validation_rejects_linked_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home, skills_root = self.copy_runtime(temporary_path)
            linked_skills = temporary_path / "linked-skills"
            external_home = temporary_path / "external-codex-home"
            shutil.move(codex_home, external_home)
            try:
                linked_skills.symlink_to(skills_root, target_is_directory=True)
                codex_home.symlink_to(external_home, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            skill_failures = VALIDATOR.validate_runtime(external_home, linked_skills.absolute())
            home_failures = VALIDATOR.validate_runtime(codex_home.absolute(), skills_root)

        self.assertTrue(any("linked path component" in failure for failure in skill_failures))
        self.assertTrue(any("linked path component" in failure for failure in home_failures))

    def test_runtime_validation_ignores_unselected_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "custom_hook.py").write_text("custom\n", encoding="utf-8")

            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

    def test_hook_registration_contract_has_two_hooks(self) -> None:
        self.assertEqual(
            VALIDATOR.HOOK_REGISTRATIONS,
            (
                ("UserPromptSubmit", "orchestration_route.py", None),
                ("SubagentStart", "subagent_scope.py", None),
            ),
        )

    def test_hook_validation_accepts_one_registration_per_event(self) -> None:
        for windows in (False, True):
            with self.subTest(windows=windows), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                hooks: dict[str, list[dict[str, object]]] = {}
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
                hooks["SessionStart"] = [{"hooks": [{"type": "command", "command": "foreign"}]}]
                hooks.setdefault("PreToolUse", []).append(
                    {
                        "matcher": "bash$",
                        "hooks": [{"type": "command", "command": "foreign"}],
                    }
                )
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                self.assertEqual(VALIDATOR.validate_hooks(codex_home, windows=windows), [])

    def test_hook_validation_rejects_duplicate_or_misplaced_registration(self) -> None:
        for windows in (False, True):
            for mutation in ("duplicate", "wrong-event", "wrong-matcher"):
                with (
                    self.subTest(windows=windows, mutation=mutation),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    codex_home = Path(temporary) / "codex-home"
                    hooks_root = codex_home / "hooks"
                    hooks_root.mkdir(parents=True)
                    hooks: dict[str, list[dict[str, object]]] = {}
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

                    event = VALIDATOR.HOOK_REGISTRATIONS[0][0]
                    group = hooks[event][0]
                    if mutation == "duplicate":
                        hooks[event].append(group.copy())
                    elif mutation == "wrong-event":
                        hooks["PreToolUse"] = hooks.pop(event)
                    else:
                        group["matcher"] = "wrong$"
                    (codex_home / "hooks.json").write_text(
                        json.dumps({"hooks": hooks}), encoding="utf-8"
                    )

                    failures = VALIDATOR.validate_hooks(codex_home, windows=windows)

                expected_count = "count is 2" if mutation == "duplicate" else "count is 0"
                self.assertTrue(any(expected_count in failure for failure in failures))

    def test_runtime_validation_rejects_retired_guard_without_hooks_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home, skills_root = self.copy_runtime(temporary_path)
            external_guard = temporary_path / "old-codex" / "hooks" / "subagent_guard.py"
            external_guard.parent.mkdir(parents=True)
            external_guard.write_text("retired\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PostToolUse": [
                                {
                                    "matcher": "wait_agent$",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": f"'/old python/python3' '{external_guard}'",
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(
            any("retired v1-shaped hook registration remains" in failure for failure in failures)
        )

    def test_hook_validation_rejects_legacy_guard_variants(self) -> None:
        legacy_groups = (
            ("PostToolUse", r"(?:functions[._]?exec|wait_agent)$"),
            ("PostToolUse", r"wait_agent$"),
            ("PreToolUse", r"close_agent$"),
            ("PreToolUse", r"send_input$|close_agent$"),
        )
        for windows in (False, True):
            for legacy_event, legacy_matcher in legacy_groups:
                with (
                    self.subTest(
                        windows=windows,
                        legacy_event=legacy_event,
                        legacy_matcher=legacy_matcher,
                    ),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    temporary_path = Path(temporary)
                    codex_home = temporary_path / "codex-home"
                    hooks_root = codex_home / "hooks"
                    hooks_root.mkdir(parents=True)
                    hooks: dict[str, list[dict[str, object]]] = {}
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

                    external_guard = temporary_path / "old-codex" / "hooks" / "subagent_guard.py"
                    external_guard.parent.mkdir(parents=True)
                    external_guard.write_text("retired\n", encoding="utf-8")
                    if windows:
                        retired_hook = {
                            "type": "command",
                            "commandWindows": subprocess.list2cmdline(
                                [r"C:\Old Python\python.exe", str(external_guard)]
                            ),
                        }
                    else:
                        retired_hook = {
                            "type": "command",
                            "command": f"'/old python/python3' '{external_guard}'",
                        }
                    hooks.setdefault(legacy_event, []).append(
                        {"matcher": legacy_matcher, "hooks": [retired_hook]}
                    )
                    (codex_home / "hooks.json").write_text(
                        json.dumps({"hooks": hooks}), encoding="utf-8"
                    )

                    failures = VALIDATOR.validate_hooks(codex_home, windows=windows)

                self.assertTrue(
                    any(
                        "retired v1-shaped hook registration remains" in failure
                        for failure in failures
                    )
                )

    def test_hook_validation_rejects_retired_guard_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            retired_target = hooks_root / "subagent_guard.py"
            retired_target.write_text("retired\n", encoding="utf-8")

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired Hook path ownership conflicts" in failure for failure in failures)
        )

    def test_hook_validation_reports_unreadable_selected_hook(self) -> None:
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
                    group["matcher"] = matcher
                hooks[event] = [group]
            (codex_home / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
            unreadable = hooks_root / "subagent_scope.py"
            original_read = VALIDATOR.Path.read_bytes

            def guarded_read(path: Path) -> bytes:
                if path == unreadable:
                    raise PermissionError("denied")
                return original_read(path)

            with mock.patch.object(VALIDATOR.Path, "read_bytes", guarded_read):
                failures = VALIDATOR.validate_hooks(codex_home, windows=windows)

        self.assertTrue(any(f"runtime hook differs: {unreadable}" in item for item in failures))

    def test_retired_scan_accepts_unhashable_foreign_matchers(self) -> None:
        for matcher in ([], {}):
            with self.subTest(matcher=matcher), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary) / "codex-home"
                codex_home.mkdir()
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": {"PostToolUse": [{"matcher": matcher, "hooks": []}]}}),
                    encoding="utf-8",
                )

                failures = VALIDATOR.retired_hook_failures(codex_home)

            self.assertEqual(failures, [])

    def test_retired_scan_reports_unreadable_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            (hooks_root / "subagent_guard.py").write_text("retired\n", encoding="utf-8")
            with mock.patch.object(VALIDATOR, "file_sha256", side_effect=PermissionError("denied")):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired Hook path unreadable" in failure for failure in failures))

    def test_retired_scan_recognizes_windows_guard_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            (hooks_root / "subagent_guard.py").write_text("retired\n", encoding="utf-8")
            windows_digest = next(
                digest
                for digest in VALIDATOR.RETIRED_HOOK_SHA256["subagent_guard.py"]
                if digest.startswith("d375")
            )
            with mock.patch.object(VALIDATOR, "file_sha256", return_value=windows_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired managed hook remains" in failure for failure in failures))

    def test_runtime_validation_rejects_legacy_v1_route_without_hooks_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "orchestration_route.py").write_text("legacy\n", encoding="utf-8")
            legacy_digest = next(iter(VALIDATOR.LEGACY_V1_ROUTE_SHA256))
            with mock.patch.object(VALIDATOR, "file_sha256", return_value=legacy_digest):
                failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("legacy managed v1 route remains" in failure for failure in failures))

    def test_retired_scan_rejects_conflicting_route_paths(self) -> None:
        for kind in ("foreign", "directory", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                route_target = hooks_root / "orchestration_route.py"
                if kind == "foreign":
                    route_target.write_text("foreign\n", encoding="utf-8")
                elif kind == "directory":
                    route_target.mkdir()
                else:
                    external = Path(temporary) / "external-route.py"
                    external.write_text("external\n", encoding="utf-8")
                    try:
                        route_target.symlink_to(external)
                    except OSError as error:
                        self.skipTest(f"symlinks unavailable: {error}")

                failures = VALIDATOR.retired_hook_failures(codex_home)

            self.assertTrue(any("legacy route path" in failure for failure in failures))

    def test_retired_scan_accepts_current_unselected_route_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            shutil.copy2(
                ROOT / "hooks" / "orchestration_route.py",
                hooks_root / "orchestration_route.py",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertEqual(failures, [])

    def test_retired_scan_rejects_legacy_route_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home = temporary_path / "codex-home"
            codex_home.mkdir()
            external_route = temporary_path / "old-codex" / "hooks" / "orchestration_route.py"
            external_route.parent.mkdir(parents=True)
            external_route.write_text("legacy\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": f"python3 '{external_route}'",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            original_digest = VALIDATOR.file_sha256
            legacy_digest = next(iter(VALIDATOR.LEGACY_V1_ROUTE_SHA256))

            def route_digest(path: Path) -> str:
                return legacy_digest if path == external_route else original_digest(path)

            with mock.patch.object(VALIDATOR, "file_sha256", side_effect=route_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("legacy v1 route registration remains" in failure for failure in failures)
        )

    def test_retired_scan_rejects_missing_route_registration_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            codex_home.mkdir()
            missing_route = Path(temporary) / "old" / "orchestration_route.py"
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": f"python3 '{missing_route}'",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("legacy route registration ownership conflicts" in failure for failure in failures)
        )

    def test_retired_scan_preserves_unrelated_hook_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python -c \"print('subagent_guard.py')\"",
                                        }
                                    ]
                                }
                            ],
                            "PreToolUse": [
                                {
                                    "matcher": "send_input$",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "echo subagent_guard.py",
                                            "commandWindows": (
                                                "python.exe -c \"print('subagent_guard.py')\""
                                            ),
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertEqual(failures, [])

    def test_retired_scan_does_not_traverse_linked_hook_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home = temporary_path / "codex-home"
            codex_home.mkdir()
            external_hooks = temporary_path / "external-hooks"
            external_hooks.mkdir()
            (external_hooks / "subagent_guard.py").write_text("external\n", encoding="utf-8")
            try:
                (codex_home / "hooks").symlink_to(external_hooks, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertEqual(len(failures), 1)
        self.assertIn("Hook directory linked or conflicting", failures[0])

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
        for windows in (False, True):
            for command_kind in ("path-substring", "path-suffix", "extra-argument"):
                with (
                    self.subTest(windows=windows, command_kind=command_kind),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    codex_home = Path(temporary) / "codex-home"
                    hooks_root = codex_home / "hooks"
                    hooks_root.mkdir(parents=True)
                    hooks: dict[str, list[dict[str, object]]] = {}
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

                    failures = VALIDATOR.validate_hooks(codex_home, windows=windows)

                self.assertTrue(any("registration count is 0" in failure for failure in failures))

    def test_expected_hook_command_uses_platform_quoting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "hook scripts" / "route.py"
            windows_command = VALIDATOR.expected_hook_command(target, windows=True)
            posix_command = VALIDATOR.expected_hook_command(target, windows=False)

        self.assertNotEqual(windows_command, posix_command)
        self.assertEqual(
            windows_command,
            subprocess.list2cmdline([str(Path(sys.executable).absolute()), str(target.absolute())]),
        )
        self.assertIn(f'"{target.absolute()}"', windows_command)
        self.assertIn(f"'{target.absolute()}'", posix_command)

    def test_hook_validation_rejects_missing_or_invalid_windows_fields(self) -> None:
        for invalid_field in (
            "missing-command",
            "invalid-command",
            "missing-commandWindows",
            "invalid-commandWindows",
            "mismatched-valid-fields",
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
                    elif invalid_field == "invalid-commandWindows":
                        hook["commandWindows"] = "invalid"
                    else:
                        hook["command"] = f"{hook['command']} "
                    group: dict[str, object] = {"hooks": [hook]}
                    if matcher is not None:
                        group["matcher"] = matcher
                    hooks[event] = [group]
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home, windows=True)

            self.assertTrue(any("registration count is 0" in failure for failure in failures))

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
