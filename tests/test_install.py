from __future__ import annotations

import importlib.abc
import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))
INSTALL_SPEC = importlib.util.spec_from_file_location(
    "codex_orchestration_installer", SCRIPTS_ROOT / "install.py"
)
assert INSTALL_SPEC is not None
assert isinstance(INSTALL_SPEC.loader, importlib.abc.InspectLoader)
INSTALL = importlib.util.module_from_spec(INSTALL_SPEC)
sys.modules[INSTALL_SPEC.name] = INSTALL
INSTALL_SPEC.loader.exec_module(INSTALL)


class InstallerTests(unittest.TestCase):
    def paths(self, temporary: str) -> tuple[Path, Path]:
        root = Path(temporary).resolve()
        return root / "codex-home", root / "skills"

    def build(
        self,
        codex_home: Path,
        skills_root: Path,
        *,
        hooks: bool = True,
        global_rules: bool = True,
    ):
        return INSTALL.build_plan(
            codex_home,
            skills_root,
            language="zh-CN",
            install_hook=hooks,
            global_rules=global_rules,
        )

    def test_full_install_is_idempotent_and_preserves_unrelated_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            user_rules = b"# Personal rules\r\n\r\nKeep this byte-for-byte.\r\n"
            (codex_home / "AGENTS.md").write_bytes(user_rules)
            unrelated_group = {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": "python user_hook.py"}],
            }
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "custom": {"preserve": True},
                        "hooks": {"SessionStart": [unrelated_group]},
                    }
                ),
                encoding="utf-8",
            )

            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            INSTALL.apply_plan(plan, install_hook=True, global_rules=True)

            installed_rules = (codex_home / "AGENTS.md").read_bytes()
            self.assertTrue(installed_rules.startswith(user_rules))
            self.assertIn(
                b"\r\n<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->\r\n",
                installed_rules,
            )
            hooks = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(hooks["custom"], {"preserve": True})
            self.assertEqual(hooks["hooks"]["SessionStart"], [unrelated_group])
            self.assertEqual(len(hooks["hooks"]["SubagentStart"]), 1)
            self.assertEqual(INSTALL.contract.validate_runtime(codex_home, skills_root), [])
            self.assertEqual(INSTALL.contract.validate_hooks(codex_home), [])
            self.assertEqual(INSTALL.contract.validate_global_rules(codex_home), [])

            second = self.build(codex_home, skills_root)
            self.assertEqual(second.conflicts, [])
            self.assertEqual(second.operations, [])

    def test_global_rules_move_to_new_active_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            canonical = INSTALL.contract.GLOBAL_RULES_TEMPLATE.read_bytes()
            (codex_home / "AGENTS.md").write_bytes(b"base\n\n" + canonical)
            (codex_home / "AGENTS.override.md").write_bytes(b"temporary override\n")

            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])
            self.assertEqual(plan.global_rules_target, codex_home / "AGENTS.override.md")
            INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertNotIn(
                INSTALL.contract.GLOBAL_RULES_START,
                (codex_home / "AGENTS.md").read_bytes(),
            )
            self.assertIn(
                INSTALL.contract.GLOBAL_RULES_START,
                (codex_home / "AGENTS.override.md").read_bytes(),
            )
            self.assertEqual(INSTALL.contract.validate_global_rules(codex_home), [])

    def test_crlf_checkout_template_renders_without_double_carriage_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            (codex_home / "AGENTS.md").write_bytes(b"personal\r\n")
            crlf_template = Path(temporary).resolve() / "global-agents-block.md"
            crlf_template.write_bytes(
                INSTALL.contract.GLOBAL_RULES_TEMPLATE.read_bytes().replace(b"\n", b"\r\n")
            )
            original_reader = INSTALL.read_managed_source

            def read_crlf_template(path: Path, label: str, plan):
                if path == crlf_template:
                    return crlf_template.read_bytes()
                return original_reader(path, label, plan)

            with (
                mock.patch.object(INSTALL.contract, "GLOBAL_RULES_TEMPLATE", crlf_template),
                mock.patch.object(INSTALL, "read_managed_source", read_crlf_template),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            installed = (codex_home / "AGENTS.md").read_bytes()
            self.assertNotIn(b"\r\r\n", installed)
            self.assertEqual(INSTALL.contract.validate_global_rules(codex_home), [])

    def test_corrupt_global_markers_block_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            original = INSTALL.contract.GLOBAL_RULES_START + b"\nmissing end\n"
            agents_path.write_bytes(original)

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("markers corrupt" in item for item in plan.conflicts))
            with self.assertRaises(RuntimeError):
                INSTALL.apply_plan(plan, install_hook=False, global_rules=True)
            self.assertEqual(agents_path.read_bytes(), original)
            self.assertEqual(list(skills_root.iterdir()), [])

    def test_hook_update_replaces_only_owned_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            target = hooks_root / "subagent_scope.py"
            target.write_text("old managed hook\n", encoding="utf-8")
            old_owned = {
                "hooks": [
                    {
                        "type": "command",
                        "command": INSTALL.contract.expected_hook_command(target),
                    }
                ]
            }
            unrelated = {"hooks": [{"type": "command", "command": "python custom.py"}]}
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SubagentStart": [unrelated, old_owned]}}),
                encoding="utf-8",
            )

            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            INSTALL.apply_plan(plan, install_hook=True, global_rules=True)

            hooks = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            groups = hooks["hooks"]["SubagentStart"]
            self.assertEqual(groups[0], unrelated)
            self.assertEqual(len(groups), 2)
            self.assertEqual(groups[1], INSTALL.desired_hook_registration(target))

    def test_authenticated_retired_hook_and_registration_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            use_windows = os.name == "nt"
            command = INSTALL.contract.expected_hook_command(retired, windows=use_windows)
            handler: dict[str, object] = {"type": "command", "command": command}
            if use_windows:
                handler["commandWindows"] = command
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "custom": True,
                        "hooks": {"PreToolUse": [{"matcher": r"send_input$", "hooks": [handler]}]},
                    }
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])
            self.assertTrue(
                any(
                    operation.kind == "delete" and operation.path == retired
                    for operation in plan.operations
                )
            )

            INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertFalse(retired.exists())
            hooks = json.loads(hooks_path.read_bytes())
            self.assertTrue(hooks["custom"])
            self.assertEqual(hooks["hooks"]["PreToolUse"], [])
            self.assertEqual(INSTALL.contract.validate_runtime(codex_home, skills_root), [])

    def test_custom_reference_blocks_authenticated_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            original_retired = b"known retired fixture\n"
            retired.write_bytes(original_retired)
            command = INSTALL.contract.expected_hook_command(retired, windows=os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            hooks_path = codex_home / "hooks.json"
            original_hooks = json.dumps(
                {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
            ).encode("utf-8")
            hooks_path.write_bytes(original_hooks)
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unconfirmed ownership" in item for item in plan.conflicts))
            with self.assertRaises(RuntimeError):
                INSTALL.apply_plan(plan, install_hook=False, global_rules=True)
            self.assertEqual(retired.read_bytes(), original_retired)
            self.assertEqual(hooks_path.read_bytes(), original_hooks)

    def test_parent_traversal_reference_blocks_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            (hooks_root / "x").mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            traversal_target = hooks_root / "x" / ".." / "subagent_guard.py"
            command = INSTALL.contract.expected_hook_command(
                traversal_target, windows=os.name == "nt"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unsafe path" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    def test_macos_case_alias_blocks_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            case_alias = hooks_root / "SUBAGENT_GUARD.PY"
            command = INSTALL.contract.expected_hook_command(case_alias, windows=os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL.sys, "platform", "darwin"),
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unconfirmed ownership" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    def test_filesystem_alias_with_different_basename_blocks_retired_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            alias = hooks_root / "custom_alias.py"
            try:
                alias.symlink_to(retired)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            command = INSTALL.contract.expected_hook_command(alias, windows=os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unconfirmed ownership" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    def test_orphan_hardlink_with_retired_hash_blocks_pure_v2_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            alias = hooks_root / "custom_alias.py"
            try:
                os.link(retired, alias)
            except OSError as error:
                self.skipTest(f"hardlinks unavailable: {error}")
            retired.unlink()
            command = INSTALL.contract.expected_hook_command(alias, windows=os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unconfirmed ownership" in item for item in plan.conflicts))
            self.assertTrue(alias.is_file())

    @unittest.skipIf(os.name == "nt", "POSIX shell glob expansion is POSIX-only")
    def test_posix_glob_reference_blocks_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            glob_target = codex_home / "hook*" / "subagent_guard.py"
            handler = {
                "type": "command",
                "command": f"{sys.executable} {glob_target}",
            }
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertEqual(list(codex_home.glob("hook*/subagent_guard.py")), [retired])
            self.assertTrue(any("unsafe path" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    def test_python_option_reference_blocks_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            arguments = [sys.executable, "-u", str(retired)]
            command = (
                " ".join(f'"{argument}"' for argument in arguments)
                if os.name == "nt"
                else shlex.join(arguments)
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertIsNone(INSTALL.contract.python_hook_script(command, windows=os.name == "nt"))
            self.assertEqual(
                INSTALL.contract.python_invoked_script(command, windows=os.name == "nt"),
                str(retired),
            )
            self.assertTrue(any("not a canonical command" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    @unittest.skipIf(os.name == "nt", "POSIX command syntax only")
    def test_environment_prefix_reference_blocks_retired_hook_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"known retired fixture\n")
            command = f"PYTHONUNBUFFERED=1 {shlex.join([sys.executable, str(retired)])}"
            handler: dict[str, object] = {"type": "command", "command": command}
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with (
                mock.patch.object(INSTALL, "sha256_bytes", return_value=known_digest),
                mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest),
            ):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertEqual(
                INSTALL.contract.python_invoked_script(command, windows=False),
                str(retired),
            )
            self.assertTrue(any("not a canonical command" in item for item in plan.conflicts))
            self.assertTrue(retired.is_file())

    def test_mixed_platform_managed_handler_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            target = hooks_root / "subagent_scope.py"
            target.write_bytes((ROOT / "hooks" / "subagent_scope.py").read_bytes())
            custom = hooks_root / "custom.py"
            custom.write_text("custom\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SubagentStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": INSTALL.contract.expected_hook_command(
                                                target,
                                                windows=INSTALL.os.name == "nt",
                                            ),
                                            "commandWindows": (
                                                INSTALL.contract.expected_hook_command(
                                                    custom, windows=True
                                                )
                                            ),
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            plan = self.build(codex_home, skills_root)

            self.assertTrue(any("mixed ownership" in item for item in plan.conflicts))

    def test_hook_is_unchanged_without_hooks_option(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            target = hooks_root / "subagent_scope.py"
            target.write_text("user-selected old copy\n", encoding="utf-8")
            hooks_bytes = json.dumps(
                {
                    "hooks": {
                        "SubagentStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": INSTALL.contract.expected_hook_command(target),
                                    }
                                ]
                            }
                        ]
                    }
                }
            ).encode("utf-8")
            (codex_home / "hooks.json").write_bytes(hooks_bytes)

            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])
            hook_operations = [
                operation
                for operation in plan.operations
                if operation.path in {target, codex_home / "hooks.json"}
            ]
            self.assertEqual(hook_operations, [])

    def test_valid_single_quoted_language_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            preferences = codex_home / "codex-orchestration" / "preferences.toml"
            preferences.parent.mkdir()
            preferences.write_text(
                "schema_version = 1\ntask_package_language = 'zh-CN'\n",
                encoding="utf-8",
            )

            plan = INSTALL.build_plan(
                codex_home,
                skills_root,
                language=None,
                install_hook=False,
                global_rules=True,
            )

            self.assertFalse(any("first install requires" in item for item in plan.conflicts))
            self.assertFalse(any(operation.path == preferences for operation in plan.operations))

    def test_unhashable_matcher_is_preserved_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            hooks_path = codex_home / "hooks.json"
            original = json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": [],
                                "hooks": [{"type": "command", "command": "python custom.py"}],
                            }
                        ]
                    }
                }
            ).encode("utf-8")
            hooks_path.write_bytes(original)

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertEqual(plan.conflicts, [])
            self.assertFalse(any(operation.path == hooks_path for operation in plan.operations))

    def test_external_retired_registration_is_a_conflict_not_a_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            external = Path(temporary).resolve() / "old" / "hooks" / "orchestration_route.py"
            external.parent.mkdir(parents=True)
            external.write_text("known old route\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": INSTALL.contract.expected_hook_command(
                                                external
                                            ),
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(INSTALL.contract.RETIRED_ROUTE_SHA256))
            with mock.patch.object(INSTALL.contract, "file_sha256", return_value=known_digest):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unconfirmed ownership" in item for item in plan.conflicts))
            self.assertFalse(any(operation.kind == "delete" for operation in plan.operations))

    def test_empty_unrelated_hook_group_is_preserved(self) -> None:
        empty_group = {"matcher": "disabled", "hooks": []}
        empty_event = "PreCompact"
        for install_hook in (False, True):
            with (
                self.subTest(install_hook=install_hook),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home, skills_root = self.paths(temporary)
                codex_home.mkdir()
                skills_root.mkdir()
                hooks_path = codex_home / "hooks.json"
                original = json.dumps(
                    {
                        "description": "user",
                        "hooks": {
                            "SubagentStart": [empty_group],
                            empty_event: [],
                        },
                    }
                ).encode("utf-8")
                hooks_path.write_bytes(original)

                plan = self.build(codex_home, skills_root, hooks=install_hook)
                self.assertEqual(plan.conflicts, [])
                INSTALL.apply_plan(plan, install_hook=install_hook, global_rules=True)

                hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
                self.assertEqual(hooks["hooks"]["SubagentStart"][0], empty_group)
                self.assertEqual(hooks["hooks"][empty_event], [])
                if install_hook:
                    self.assertEqual(len(hooks["hooks"]["SubagentStart"]), 2)
                else:
                    self.assertEqual(hooks_path.read_bytes(), original)

    def test_missing_hooks_field_is_created_only_when_hook_is_selected(self) -> None:
        for install_hook in (False, True):
            with (
                self.subTest(install_hook=install_hook),
                tempfile.TemporaryDirectory() as temporary,
            ):
                codex_home, skills_root = self.paths(temporary)
                codex_home.mkdir()
                skills_root.mkdir()
                hooks_path = codex_home / "hooks.json"
                original = b'{"custom":true}'
                hooks_path.write_bytes(original)

                plan = self.build(codex_home, skills_root, hooks=install_hook)
                self.assertEqual(plan.conflicts, [])
                INSTALL.apply_plan(plan, install_hook=install_hook, global_rules=True)

                if install_hook:
                    hooks = json.loads(hooks_path.read_bytes())
                    self.assertTrue(hooks["custom"])
                    self.assertEqual(len(hooks["hooks"]["SubagentStart"]), 1)
                else:
                    self.assertEqual(hooks_path.read_bytes(), original)

    def test_utf8_bom_hooks_config_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_bytes(b'\xef\xbb\xbf{"custom":true,"hooks":{}}')

            plan = self.build(codex_home, skills_root, hooks=True)
            self.assertEqual(plan.conflicts, [])
            INSTALL.apply_plan(plan, install_hook=True, global_rules=True)

            hooks = json.loads(hooks_path.read_bytes())
            self.assertTrue(hooks["custom"])
            self.assertEqual(INSTALL.contract.validate_hooks(codex_home), [])

    def test_duplicate_hook_json_keys_are_a_planning_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            (codex_home / "hooks.json").write_bytes(b'{"hooks":{},"hooks":{}}')

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("duplicate JSON key" in item for item in plan.conflicts))

    def test_linked_managed_target_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            external = Path(temporary).resolve() / "external-agents.md"
            external.write_text("external\n", encoding="utf-8")
            try:
                (codex_home / "AGENTS.md").symlink_to(external)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("linked or conflicting" in item for item in plan.conflicts))

    def test_linked_managed_source_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            checkout = root / "checkout"
            checkout.mkdir()
            external = root / "external-skill.md"
            external.write_text("---\nname: codex-orchestration\n---\n", encoding="utf-8")
            try:
                (checkout / "SKILL.md").symlink_to(external)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            codex_home = root / "codex-home"
            skills_root = root / "skills"
            codex_home.mkdir()
            skills_root.mkdir()
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)

            with mock.patch.object(INSTALL, "ROOT", checkout):
                INSTALL.plan_skill(
                    plan,
                    "codex-orchestration",
                    checkout,
                    skills_root / "codex-orchestration",
                )

            self.assertTrue(any("linked source path" in item for item in plan.conflicts))

    def test_linked_parent_of_selected_root_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            external = root / "external"
            external.mkdir()
            linked_parent = root / "linked-parent"
            try:
                linked_parent.symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            skills_root = root / "skills"
            skills_root.mkdir()

            plan = self.build(linked_parent / "codex-home", skills_root, hooks=False)

            self.assertTrue(
                any("linked or unsafe path component" in item for item in plan.conflicts)
            )
            self.assertEqual(list(external.iterdir()), [])

    def test_parent_traversal_segment_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "nested" / ".." / "codex-home"
            skills_root = root / "skills"
            skills_root.mkdir()

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("unsafe path component" in item for item in plan.conflicts))

    @unittest.skipUnless(os.name == "nt", "NTFS junctions are Windows-only")
    def test_windows_junction_root_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            external = root / "external"
            external.mkdir()
            junction = root / "codex-home"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(external)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            skills_root = root / "skills"
            skills_root.mkdir()

            plan = self.build(junction, skills_root, hooks=False)

            self.assertTrue(any("linked or conflicting" in item for item in plan.conflicts))

    def test_unreadable_global_rules_are_a_bounded_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            target = codex_home / "AGENTS.md"
            target.write_text("personal\n", encoding="utf-8")
            original_read = Path.read_bytes

            def unreadable(path: Path) -> bytes:
                if path == target:
                    raise PermissionError("denied")
                return original_read(path)

            with mock.patch.object(Path, "read_bytes", unreadable):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(
                any("global instructions unreadable" in item for item in plan.conflicts)
            )

    def test_unreadable_retired_hook_is_a_bounded_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            target = hooks_root / "subagent_guard.py"
            target.write_text("retired\n", encoding="utf-8")
            original_read = Path.read_bytes

            def unreadable(path: Path) -> bytes:
                if path == target:
                    raise PermissionError("denied")
                return original_read(path)

            with mock.patch.object(Path, "read_bytes", unreadable):
                plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("retired Hook path unreadable" in item for item in plan.conflicts))

    def test_failed_verification_rolls_back_every_completed_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_bytes(b"original\n")
            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])

            with (
                mock.patch.object(INSTALL, "verification_failures", return_value=["boom"]),
                self.assertRaises(RuntimeError),
            ):
                INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertEqual(agents_path.read_bytes(), b"original\n")
            self.assertEqual(list(skills_root.iterdir()), [])
            self.assertFalse((codex_home / "agents").exists())

    def test_rollback_refuses_a_parent_link_created_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            managed_parent = skills_root / "managed"
            managed_parent.mkdir()
            target = managed_parent / "file.txt"
            target.write_bytes(b"old\n")
            external = Path(temporary).resolve() / "external"
            external.mkdir()
            saved_parent = skills_root / "managed-saved"
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)
            plan.operations.append(INSTALL.Operation("write", target, "test", b"new\n", b"old\n"))
            real_atomic_write = INSTALL.atomic_write

            def write_then_swap(path: Path, content: bytes) -> None:
                real_atomic_write(path, content)
                managed_parent.rename(saved_parent)
                managed_parent.symlink_to(external, target_is_directory=True)

            try:
                with (
                    mock.patch.object(INSTALL, "atomic_write", write_then_swap),
                    self.assertRaisesRegex(RuntimeError, "rollback refused conflicting target"),
                ):
                    INSTALL.apply_plan(plan, install_hook=False, global_rules=False)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            self.assertEqual((saved_parent / "file.txt").read_bytes(), b"new\n")
            self.assertEqual(list(external.iterdir()), [])

    def test_apply_rejects_a_target_changed_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_bytes(b"planned\n")
            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])
            agents_path.write_bytes(b"concurrent edit\n")

            with self.assertRaisesRegex(RuntimeError, "changed after planning"):
                INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertEqual(agents_path.read_bytes(), b"concurrent edit\n")
            self.assertEqual(list(skills_root.iterdir()), [])

    def test_apply_rejects_a_parent_link_created_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            external = Path(temporary).resolve() / "external"
            external.mkdir()
            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])
            try:
                (skills_root / "codex-orchestration").symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            with self.assertRaisesRegex(RuntimeError, "linked or conflicting"):
                INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertEqual(list(external.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not the Windows ACL contract")
    def test_existing_file_mode_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_bytes(b"personal\n")
            agents_path.chmod(0o640)
            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            self.assertEqual(stat.S_IMODE(agents_path.stat().st_mode), 0o640)

    @unittest.skipUnless(os.name == "nt", "Windows file attributes are Windows-only")
    def test_existing_windows_file_attributes_are_preserved(self) -> None:
        import ctypes

        file_attribute_hidden = 0x2
        invalid_file_attributes = 0xFFFFFFFF
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        get_attributes = kernel32.GetFileAttributesW
        get_attributes.argtypes = (ctypes.c_wchar_p,)
        get_attributes.restype = ctypes.c_uint32
        set_attributes = kernel32.SetFileAttributesW
        set_attributes.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32)
        set_attributes.restype = ctypes.c_int

        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_bytes(b"personal\n")
            api_path = INSTALL.windows_extended_path(agents_path)
            original_attributes = get_attributes(api_path)
            self.assertNotEqual(original_attributes, invalid_file_attributes)
            self.assertTrue(set_attributes(api_path, original_attributes | file_attribute_hidden))
            plan = self.build(codex_home, skills_root, hooks=False)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, install_hook=False, global_rules=True)

            installed_attributes = get_attributes(api_path)
            self.assertNotEqual(installed_attributes, invalid_file_attributes)
            self.assertTrue(installed_attributes & file_attribute_hidden)

    def test_windows_extended_paths_cover_drive_and_unc_forms(self) -> None:
        self.assertEqual(
            INSTALL.windows_extended_path(r"C:\runtime\file"),
            r"\\?\C:\runtime\file",
        )

    def test_overlong_windows_target_is_a_planning_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            skills_root = root / "skills"
            codex_home.mkdir()
            skills_root.mkdir()
            target = skills_root / ("a" * 230) / "file.txt"
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)

            with mock.patch.object(INSTALL.os, "name", "nt"):
                accepted = INSTALL.regular_target(target, skills_root, "test target", plan)

            self.assertFalse(accepted)
            self.assertTrue(any("Windows path limit" in item for item in plan.conflicts))

    def test_windows_target_reserves_same_directory_temporary_path_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            skills_root = root / "skills"
            codex_home.mkdir()
            skills_root.mkdir()
            target_length = INSTALL.WINDOWS_CONSERVATIVE_PATH_LIMIT - 10
            padding_length = target_length - len(str(skills_root / "file.txt")) - 1
            self.assertGreater(padding_length, 0)
            target = skills_root / ("a" * padding_length) / "file.txt"
            self.assertLess(len(str(target.absolute())), INSTALL.WINDOWS_CONSERVATIVE_PATH_LIMIT)
            self.assertGreaterEqual(
                len(
                    str(
                        INSTALL.installer_temporary_path(
                            target, "0" * INSTALL.TEMPORARY_TOKEN_LENGTH
                        ).absolute()
                    )
                ),
                INSTALL.WINDOWS_CONSERVATIVE_PATH_LIMIT,
            )
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)

            with mock.patch.object(INSTALL.os, "name", "nt"):
                accepted = INSTALL.regular_target(target, skills_root, "test target", plan)

            self.assertFalse(accepted)
            self.assertTrue(any("Windows path limit" in item for item in plan.conflicts))

    def test_overlong_windows_retired_target_is_not_planned_for_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / ("a" * 80) / ("b" * 80) / ("c" * 40)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            retired = hooks_root / "subagent_guard.py"
            retired.write_bytes(b"retired\n")
            skills_root = root / "skills"
            skills_root.mkdir()
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)

            with mock.patch.object(INSTALL.os, "name", "nt"):
                INSTALL.plan_retired_hook_files(plan)

            self.assertTrue(any("Windows path limit" in item for item in plan.conflicts))
            self.assertFalse(any(operation.kind == "delete" for operation in plan.operations))
        self.assertEqual(
            INSTALL.windows_extended_path(r"\\server\share\file"),
            r"\\?\UNC\server\share\file",
        )
        self.assertEqual(
            INSTALL.windows_extended_path(r"\\?\C:\runtime\file"),
            r"\\?\C:\runtime\file",
        )

    def test_cli_dry_run_does_not_create_roots_and_missing_language_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary) / "dry-run"
            codex_home = runtime_root / "codex-home"
            skills_root = runtime_root / "skills"
            command = [
                sys.executable,
                str(SCRIPTS_ROOT / "install.py"),
                "--codex-home",
                str(codex_home),
                "--skills-root",
                str(skills_root),
            ]

            dry_run = subprocess.run(
                [*command, "--language", "en"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
            self.assertFalse(runtime_root.exists())

            missing_language = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                missing_language.returncode,
                2,
                missing_language.stdout + missing_language.stderr,
            )
            self.assertIn("first install requires --language", missing_language.stdout)
            self.assertFalse(runtime_root.exists())

    def test_cli_installs_missing_roots_with_spaces_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary) / "runtime with spaces"
            codex_home = runtime_root / "codex-home"
            skills_root = runtime_root / "skills"
            command = [
                sys.executable,
                str(SCRIPTS_ROOT / "install.py"),
                "--codex-home",
                str(codex_home),
                "--skills-root",
                str(skills_root),
                "--language",
                "zh-CN",
                "--hooks",
                "--apply",
            ]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            effective_home = INSTALL.contract.canonical_selected_root(codex_home)
            effective_skills = INSTALL.contract.canonical_selected_root(skills_root)
            self.assertTrue((effective_home / "AGENTS.md").is_file())
            self.assertTrue((effective_skills / "codex-orchestration" / "SKILL.md").is_file())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(effective_home.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(effective_skills.stat().st_mode), 0o700)

            second_command = [item for item in command if item not in {"--language", "zh-CN"}]
            second_command.remove("--apply")
            second = subprocess.run(second_command, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("[CURRENT] no managed runtime changes", second.stdout)

            without_global = subprocess.run(
                [*second_command, "--no-global-rules"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                without_global.returncode, 0, without_global.stdout + without_global.stderr
            )
            self.assertIn("Global rules: unchanged", without_global.stdout)

    def test_retired_file_requires_authenticated_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            skills_root.mkdir()
            retired = hooks_root / "subagent_guard.py"
            retired.write_text("foreign\n", encoding="utf-8")

            plan = self.build(codex_home, skills_root, hooks=False)

            self.assertTrue(any("ownership conflict" in item for item in plan.conflicts))


if __name__ == "__main__":
    unittest.main()
