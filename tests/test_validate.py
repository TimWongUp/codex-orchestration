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
        self.assertIn("interrupt or close only when", route["additionalContext"])

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
            events = {
                "UserPromptSubmit": "orchestration_route.py",
                "SubagentStart": "subagent_scope.py",
            }
            hooks: dict[str, list[dict[str, object]]] = {}
            command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
            for event, script in events.items():
                shutil.copy2(ROOT / "hooks" / script, hooks_root / script)
                hooks[event] = [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                command_field: VALIDATOR.expected_hook_command(hooks_root / script),
                            }
                        ]
                    }
                ]
            hooks["SessionStart"] = [{"hooks": [{"type": "command", "command": "foreign"}]}]
            (codex_home / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

            self.assertEqual(VALIDATOR.validate_hooks(codex_home), [])

    def test_hook_validation_rejects_non_exact_commands(self) -> None:
        for command_kind in ("path-substring", "path-suffix", "extra-argument"):
            with (
                self.subTest(command_kind=command_kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home = Path(temporary) / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                events = {
                    "UserPromptSubmit": "orchestration_route.py",
                    "SubagentStart": "subagent_scope.py",
                }
                hooks: dict[str, list[dict[str, object]]] = {}
                command_field = "commandWindows" if VALIDATOR.os.name == "nt" else "command"
                for event, script in events.items():
                    target = hooks_root / script
                    shutil.copy2(ROOT / "hooks" / script, target)
                    if command_kind == "path-substring":
                        command = f'echo "{target}"'
                    elif command_kind == "path-suffix":
                        command = VALIDATOR.expected_hook_command(Path(f"{target}.disabled"))
                    else:
                        command = f"{VALIDATOR.expected_hook_command(target)} extra"
                    hooks[event] = [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    command_field: command,
                                }
                            ]
                        }
                    ]
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": hooks}), encoding="utf-8"
                )

                failures = VALIDATOR.validate_hooks(codex_home)

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
