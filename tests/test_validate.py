from __future__ import annotations

import importlib.util
import json
import os
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
        self.assertIn("continue non-overlapping main work", route["additionalContext"])
        self.assertIn("If a wait times out", route["additionalContext"])
        self.assertIn("USER_REQUESTED_INTERRUPT:", route["additionalContext"])
        self.assertIn("terminal status", route["additionalContext"])

        for payload, expected in (
            ('{"agent_type":"worker"}', "complete canonical"),
            ('{"agentType":"explorer"}', "read-only"),
            ('{"agent_type":"unknown"}', "read-only"),
            ("[]", "read-only"),
        ):
            with self.subTest(payload=payload):
                scope = run_hook("subagent_scope.py", payload)
                self.assertEqual(scope["hookEventName"], "SubagentStart")
                self.assertIn(expected, scope["additionalContext"])
                if "worker" in payload:
                    for field in VALIDATOR.WORKER_PACKAGE_FIELDS:
                        self.assertIn(field, scope["additionalContext"])

    def test_subagent_guard_blocks_interrupt_and_running_close(self) -> None:
        def run_guard(payload: dict[str, object], state_root: Path) -> dict[str, object]:
            environment = dict(os.environ)
            environment["CODEX_ORCHESTRATION_STATE_DIR"] = str(state_root)
            result = subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "subagent_guard.py")],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return cast(dict[str, object], json.loads(result.stdout))

        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            interrupt = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "multi_agent_v1send_input",
                    "tool_input": {"target": "agent-a", "interrupt": True, "message": "stop"},
                },
                state_root,
            )
            self.assertEqual(
                cast(dict[str, object], interrupt["hookSpecificOutput"])[
                    "permissionDecision"
                ],
                "deny",
            )

            malformed_interrupt = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "multi_agent_v1__send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": "true",
                        "message": "stop",
                    },
                },
                state_root,
            )
            self.assertEqual(
                cast(dict[str, object], malformed_interrupt["hookSpecificOutput"])[
                    "permissionDecision"
                ],
                "deny",
            )

            authorized = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": True,
                        "message": "USER_REQUESTED_INTERRUPT: stop",
                    },
                },
                state_root,
            )
            self.assertEqual(authorized, {})

            queued = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": False,
                        "message": "continue when ready",
                    },
                },
                state_root,
            )
            self.assertEqual(queued, {})

            authorized_items = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": True,
                        "items": [
                            {
                                "type": "text",
                                "text": "USER_REQUESTED_INTERRUPT: replace reviewer",
                            }
                        ],
                    },
                },
                state_root,
            )
            self.assertEqual(authorized_items, {})

            unmarked_items = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "send_input",
                    "tool_input": {
                        "target": "agent-a",
                        "interrupt": True,
                        "items": [{"type": "text", "text": "replace reviewer"}],
                    },
                },
                state_root,
            )
            self.assertEqual(
                cast(dict[str, object], unmarked_items["hookSpecificOutput"])[
                    "permissionDecision"
                ],
                "deny",
            )

            close_running = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "close_agent",
                    "tool_input": {"target": "agent-a"},
                },
                state_root,
            )
            self.assertEqual(
                cast(dict[str, object], close_running["hookSpecificOutput"])[
                    "permissionDecision"
                ],
                "deny",
            )

            run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PostToolUse",
                    "tool_name": "wait_agent",
                    "tool_response": {
                        "status": {"agent-a": "running"},
                        "timed_out": True,
                    },
                },
                state_root,
            )
            self.assertEqual(
                cast(
                    dict[str, object],
                    run_guard(
                        {
                            "session_id": "session-a",
                            "hook_event_name": "PreToolUse",
                            "tool_name": "close_agent",
                            "tool_input": {"target": "agent-a"},
                        },
                        state_root,
                    )["hookSpecificOutput"],
                )["permissionDecision"],
                "deny",
            )

            run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PostToolUse",
                    "tool_name": "multi_agent_v1wait_agent",
                    "tool_response": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "status": {
                                        "agent-a": {"completed": "review complete"}
                                    },
                                    "timed_out": False,
                                }
                            ),
                        }
                    ],
                },
                state_root,
            )
            close_completed = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "multi_agent_v1close_agent",
                    "tool_input": {"target": "agent-a"},
                },
                state_root,
            )
            self.assertEqual(close_completed, {})

            self.assertEqual(
                run_guard(
                    {
                        "session_id": "session-a",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "send_input",
                        "tool_input": {
                            "target": "agent-a",
                            "interrupt": False,
                            "message": "start another review",
                        },
                    },
                    state_root,
                ),
                {},
            )
            restarted_close = run_guard(
                {
                    "session_id": "session-a",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "close_agent",
                    "tool_input": {"target": "agent-a"},
                },
                state_root,
            )
            self.assertEqual(
                cast(dict[str, object], restarted_close["hookSpecificOutput"])[
                    "permissionDecision"
                ],
                "deny",
            )

            for index, terminal_status in enumerate(
                (
                    {"completed": None},
                    {"errored": "review failed"},
                    "interrupted",
                    "shutdown",
                    "not_found",
                )
            ):
                agent_id = f"terminal-agent-{index}"
                with self.subTest(terminal_status=terminal_status):
                    run_guard(
                        {
                            "session_id": "session-a",
                            "hook_event_name": "PostToolUse",
                            "tool_name": "wait_agent",
                            "tool_response": {
                                "status": {agent_id: terminal_status},
                                "timed_out": False,
                            },
                        },
                        state_root,
                    )
                    self.assertEqual(
                        run_guard(
                            {
                                "session_id": "session-a",
                                "hook_event_name": "PreToolUse",
                                "tool_name": "close_agent",
                                "tool_input": {"target": agent_id},
                            },
                            state_root,
                        ),
                        {},
                    )

    def test_runtime_validation_accepts_copied_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

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
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            hooks: dict[str, list[dict[str, object]]] = {}
            command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
            for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                shutil.copy2(ROOT / "hooks" / script, hooks_root / script)
                group: dict[str, object] = {
                    "hooks": [
                        {
                            "type": "command",
                            command_field: VALIDATOR.expected_hook_command(hooks_root / script),
                        }
                    ]
                }
                if matcher is not None:
                    group["matcher"] = matcher
                hooks[event] = [group]
            hooks["SessionStart"] = [{"hooks": [{"type": "command", "command": "foreign"}]}]
            (codex_home / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

            self.assertEqual(VALIDATOR.validate_hooks(codex_home), [])

    def test_runtime_cli_validates_selected_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary))
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            hooks: dict[str, list[dict[str, object]]] = {}
            command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
            for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                target = hooks_root / script
                shutil.copy2(ROOT / "hooks" / script, target)
                group: dict[str, object] = {
                    "hooks": [
                        {
                            "type": "command",
                            command_field: VALIDATOR.expected_hook_command(target),
                        }
                    ]
                }
                if matcher is not None:
                    group["matcher"] = matcher
                hooks[event] = [group]
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": hooks}), encoding="utf-8"
            )

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
                command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
                for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                    target = hooks_root / script
                    shutil.copy2(ROOT / "hooks" / script, target)
                    if command_kind == "path-substring":
                        command = f'echo "{target}"'
                    elif command_kind == "path-suffix":
                        command = VALIDATOR.expected_hook_command(Path(f"{target}.disabled"))
                    else:
                        command = f"{VALIDATOR.expected_hook_command(target)} extra"
                    group: dict[str, object] = {
                        "hooks": [
                            {
                                "type": "command",
                                command_field: command,
                            }
                        ]
                    }
                    if matcher is not None:
                        group["matcher"] = matcher
                    hooks[event] = [group]
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home)

            self.assertTrue(any("registration count is 0" in failure for failure in failures))

    def test_hook_validation_rejects_guard_matcher_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            hooks: dict[str, list[dict[str, object]]] = {}
            command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
            for event, script, matcher in VALIDATOR.HOOK_REGISTRATIONS:
                target = hooks_root / script
                shutil.copy2(ROOT / "hooks" / script, target)
                group: dict[str, object] = {
                    "hooks": [
                        {
                            "type": "command",
                            command_field: VALIDATOR.expected_hook_command(target),
                        }
                    ]
                }
                if matcher is not None:
                    group["matcher"] = "Agent" if event == "PreToolUse" else matcher
                hooks[event] = [group]
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": hooks}), encoding="utf-8"
            )

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
