from __future__ import annotations

import contextlib
import importlib.abc
import importlib.util
import io
import os
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
        global_rules: bool = True,
    ):
        return INSTALL.build_plan(
            codex_home,
            skills_root,
            language="zh-CN",
            global_rules=global_rules,
        )

    def build_uninstall(self, codex_home: Path, skills_root: Path):
        return INSTALL.build_uninstall_plan(codex_home, skills_root)

    def test_full_install_is_idempotent_and_preserves_unrelated_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_root = codex_home / "agents"
            agents_root.mkdir()
            legacy_agent = agents_root / "frontend-design.toml"
            legacy_agent.write_text("user-owned legacy profile\n", encoding="utf-8")
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            legacy_hook = hooks_root / "subagent_guard.py"
            legacy_hook.write_text("user-owned legacy hook\n", encoding="utf-8")
            user_rules = b"# Personal rules\r\n\r\nKeep this byte-for-byte.\r\n"
            (codex_home / "AGENTS.md").write_bytes(user_rules)
            hooks_content = b"{invalid but user-owned\n"
            (codex_home / "hooks.json").write_bytes(hooks_content)
            independent_skill = skills_root / "simplicity-review" / "SKILL.md"
            independent_skill.parent.mkdir()
            independent_skill.write_text("independently managed\n", encoding="utf-8")

            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            INSTALL.apply_plan(plan, global_rules=True)

            installed_rules = (codex_home / "AGENTS.md").read_bytes()
            self.assertTrue(installed_rules.startswith(user_rules))
            self.assertIn(
                b"\r\n<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->\r\n",
                installed_rules,
            )
            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_content)
            self.assertEqual(
                legacy_agent.read_text(encoding="utf-8"), "user-owned legacy profile\n"
            )
            self.assertEqual(legacy_hook.read_text(encoding="utf-8"), "user-owned legacy hook\n")
            self.assertEqual(
                independent_skill.read_text(encoding="utf-8"), "independently managed\n"
            )
            self.assertTrue((skills_root / "codex-review-gate" / "SKILL.md").is_file())
            self.assertTrue(
                (
                    skills_root
                    / "codex-orchestration"
                    / "references"
                    / "read-only-collaboration.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    skills_root
                    / "codex-orchestration"
                    / "references"
                    / "collaboration-lifecycle.md"
                ).is_file()
            )
            self.assertEqual(INSTALL.contract.validate_runtime(codex_home, skills_root), [])
            self.assertEqual(INSTALL.contract.validate_global_rules(codex_home), [])

            second = self.build(codex_home, skills_root)
            self.assertEqual(second.conflicts, [])
            self.assertEqual(second.operations, [])

    def test_install_plan_reports_local_model_routing_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            plan = self.build(codex_home, skills_root)
            routing_path = codex_home / "codex-orchestration" / "model-routing.toml"

            missing_output = io.StringIO()
            with contextlib.redirect_stdout(missing_output):
                INSTALL.print_plan(plan, global_rules=True)

            self.assertIn(
                "Model routing: not configured; subagents request inheritance from current "
                "Codex settings (resolved model unconfirmed)",
                missing_output.getvalue(),
            )
            self.assertIn(
                f"explicit approval before creating: {routing_path}",
                missing_output.getvalue(),
            )

            template = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")
            route = (
                template.replace('"TASK_KIND"', '"worker-round-three"')
                .replace('"ROLE_NAME"', '"worker"')
                .replace('"MODEL_ID_OVERRIDE"', '"model-override"')
                .replace('"MODEL_ID_PRIMARY_1"', '"model-primary-1"')
                .replace('"MODEL_ID_PRIMARY_2"', '"model-primary-2"')
                .replace('"MODEL_ID_FALLBACK"', '"model-fallback"')
                .replace('"MODEL_ID_PRIMARY"', '"model-role-primary"')
                .replace('"REASONING_LEVEL"', '"high"')
                .replace('"SERVICE_TIER"', '"standard"')
            )
            routing_path.parent.mkdir(parents=True)
            routing_path.write_text(route, encoding="utf-8")
            present_plan = self.build(codex_home, skills_root)
            present_output = io.StringIO()
            with contextlib.redirect_stdout(present_output):
                INSTALL.print_plan(present_plan, global_rules=True)

            self.assertIn(
                f"Model routing: preserve validated local configuration: {routing_path}",
                present_output.getvalue(),
            )
            self.assertNotIn("request inheritance", present_output.getvalue())

            routing_path.write_text("invalid local route\n", encoding="utf-8")
            invalid_plan = self.build(codex_home, skills_root)
            self.assertTrue(
                any("local model routing invalid" in item for item in invalid_plan.conflicts)
            )
            invalid_output = io.StringIO()
            with contextlib.redirect_stdout(invalid_output):
                INSTALL.print_plan(invalid_plan, global_rules=True)
            self.assertIn(
                f"Model routing: invalid or conflicting local path: {routing_path}",
                invalid_output.getvalue(),
            )

            routing_path.unlink()
            routing_path.mkdir()
            directory_plan = self.build(codex_home, skills_root)
            self.assertTrue(
                any(
                    "local model routing linked or conflicting" in item
                    for item in directory_plan.conflicts
                )
            )

    def test_uninstall_removes_only_current_managed_projection_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            personal_rules = b"# Personal rules\n"
            (codex_home / "AGENTS.md").write_bytes(personal_rules)
            hooks_content = b"{unmanaged hooks}\n"
            (codex_home / "hooks.json").write_bytes(hooks_content)
            agents_root = codex_home / "agents"
            agents_root.mkdir()
            unmanaged_agent = agents_root / "personal.toml"
            unmanaged_agent.write_bytes(b"personal agent\n")

            install = self.build(codex_home, skills_root)
            self.assertEqual(install.conflicts, [])
            INSTALL.apply_plan(install, global_rules=True)

            local_root = codex_home / "codex-orchestration"
            model_route = local_root / "model-routing.toml"
            model_route.write_bytes(b"local model route\n")
            independent_skill_file = skills_root / "simplicity-review" / "SKILL.md"
            independent_skill_file.parent.mkdir()
            independent_skill_file.write_bytes(b"independently managed\n")
            unmanaged_skill_file = skills_root / "codex-orchestration" / "personal-note.md"
            unmanaged_skill_file.write_bytes(b"preserve inside managed directory\n")
            rules_path = codex_home / "AGENTS.md"
            rules_path.write_bytes(
                rules_path.read_bytes().replace(
                    b"## Agent orchestration", b"## Stale agent orchestration"
                )
            )

            plan = self.build_uninstall(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            self.assertTrue(any(operation.content is None for operation in plan.operations))
            INSTALL.apply_plan(plan, global_rules=True, uninstall=True)

            for target in INSTALL.managed_runtime_targets(plan):
                self.assertFalse(INSTALL.lexists(target), target)
            self.assertNotIn(
                INSTALL.contract.GLOBAL_RULES_START,
                (codex_home / "AGENTS.md").read_bytes(),
            )
            self.assertTrue((codex_home / "AGENTS.md").read_bytes().startswith(personal_rules))
            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_content)
            self.assertEqual(unmanaged_agent.read_bytes(), b"personal agent\n")
            self.assertEqual(model_route.read_bytes(), b"local model route\n")
            self.assertEqual(independent_skill_file.read_bytes(), b"independently managed\n")
            self.assertEqual(
                unmanaged_skill_file.read_bytes(), b"preserve inside managed directory\n"
            )
            self.assertFalse((skills_root / "codex-review-gate").exists())

            second = self.build_uninstall(codex_home, skills_root)
            self.assertEqual(second.conflicts, [])
            self.assertEqual(second.operations, [])

    def test_uninstall_rejects_changed_managed_file_before_any_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            install = self.build(codex_home, skills_root)
            self.assertEqual(install.conflicts, [])
            INSTALL.apply_plan(install, global_rules=True)
            changed = codex_home / "agents" / "worker.toml"
            changed.write_bytes(b"user changed this managed profile\n")

            plan = self.build_uninstall(codex_home, skills_root)

            self.assertTrue(any("changed; refusing removal" in item for item in plan.conflicts))
            with self.assertRaises(RuntimeError):
                INSTALL.apply_plan(plan, global_rules=True, uninstall=True)
            self.assertEqual(changed.read_bytes(), b"user changed this managed profile\n")
            self.assertTrue((skills_root / "codex-orchestration" / "SKILL.md").is_file())
            self.assertIn(
                INSTALL.contract.GLOBAL_RULES_START,
                (codex_home / "AGENTS.md").read_bytes(),
            )

    def test_uninstall_verification_failure_restores_staged_files_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            install = self.build(codex_home, skills_root)
            self.assertEqual(install.conflicts, [])
            INSTALL.apply_plan(install, global_rules=True)
            rules_before = (codex_home / "AGENTS.md").read_bytes()
            worker = codex_home / "agents" / "worker.toml"
            worker_before = worker.read_bytes()
            plan = self.build_uninstall(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])

            with (
                mock.patch.object(
                    INSTALL, "uninstall_verification_failures", return_value=["boom"]
                ),
                self.assertRaises(RuntimeError),
            ):
                INSTALL.apply_plan(plan, global_rules=True, uninstall=True)

            self.assertEqual(worker.read_bytes(), worker_before)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), rules_before)
            self.assertEqual(INSTALL.contract.validate_runtime(codex_home, skills_root), [])
            self.assertEqual(INSTALL.contract.validate_global_rules(codex_home), [])

    def test_uninstall_rejects_runtime_roots_overlapping_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            cases = (
                (ROOT, skills_root),
                (codex_home, ROOT / "skills"),
                (ROOT.parent, skills_root),
            )
            for selected_home, selected_skills in cases:
                with self.subTest(
                    codex_home=selected_home,
                    skills_root=selected_skills,
                ):
                    plan = self.build_uninstall(selected_home, selected_skills)
                    self.assertTrue(
                        any("overlaps source checkout" in item for item in plan.conflicts)
                    )
                    self.assertEqual(plan.operations, [])

            case_variant = ROOT.with_name(ROOT.name.swapcase())
            try:
                same_checkout = os.path.samefile(case_variant, ROOT)
            except OSError:
                same_checkout = False
            if same_checkout:
                plan = self.build_uninstall(case_variant, skills_root)
                self.assertTrue(any("overlaps source checkout" in item for item in plan.conflicts))
                self.assertEqual(plan.operations, [])

    def test_staged_cleanup_failure_is_a_committed_uninstall_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            install = self.build(codex_home, skills_root)
            self.assertEqual(install.conflicts, [])
            INSTALL.apply_plan(install, global_rules=True)
            plan = self.build_uninstall(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            real_unlink = Path.unlink
            retained: list[Path] = []

            def fail_one_staged_cleanup(path: Path, *args, **kwargs) -> None:
                if not retained and ".codex-orchestration-" in path.name:
                    retained.append(path)
                    raise PermissionError("forced staged cleanup failure")
                real_unlink(path, *args, **kwargs)

            with mock.patch.object(Path, "unlink", fail_one_staged_cleanup):
                warnings = INSTALL.apply_plan(plan, global_rules=True, uninstall=True)

            self.assertEqual(len(warnings), 1)
            self.assertIn("after verified commit", warnings[0])
            self.assertEqual(len(retained), 1)
            self.assertTrue(retained[0].is_file())
            for target in INSTALL.managed_runtime_targets(plan):
                self.assertFalse(INSTALL.lexists(target), target)

    def test_first_install_without_global_rules_preserves_global_files_and_hooks(self) -> None:
        cases = (
            ("base-exists", "AGENTS.md", b"user-owned base\n"),
            ("override-exists", "AGENTS.override.md", b"user-owned override\n"),
        )
        for label, existing_name, existing_content in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                codex_home, skills_root = self.paths(temporary)
                codex_home.mkdir()
                skills_root.mkdir()
                hooks_content = (
                    b'{"hooks": { "SessionStart": [ { "hooks": [ '
                    b'{ "command": "echo ok", "type": "command" } ], '
                    b'"matcher": "startup" } ] }, "custom": 1}\n'
                )
                hooks_path = codex_home / "hooks.json"
                hooks_path.write_bytes(hooks_content)
                global_paths = {
                    name: codex_home / name for name in ("AGENTS.md", "AGENTS.override.md")
                }
                global_paths[existing_name].write_bytes(existing_content)
                global_before = {
                    name: path.read_bytes() if path.exists() else None
                    for name, path in global_paths.items()
                }

                plan = self.build(codex_home, skills_root, global_rules=False)
                self.assertEqual(plan.conflicts, [])
                INSTALL.apply_plan(plan, global_rules=False)

                global_after = {
                    name: path.read_bytes() if path.exists() else None
                    for name, path in global_paths.items()
                }
                self.assertEqual(hooks_path.read_bytes(), hooks_content)
                self.assertEqual(global_after, global_before)
                self.assertEqual(INSTALL.contract.validate_runtime(codex_home, skills_root), [])

    def test_no_global_rules_rejects_a_stale_managed_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            stale = b"\n".join(
                (
                    INSTALL.contract.GLOBAL_RULES_START,
                    b"## Agent orchestration",
                    b"- Load the old built-in Review gate.",
                    INSTALL.contract.GLOBAL_RULES_END,
                    b"",
                )
            )
            (codex_home / "AGENTS.md").write_bytes(stale)

            plan = self.build(codex_home, skills_root, global_rules=False)

            self.assertTrue(
                any("managed global-rules block is stale" in item for item in plan.conflicts)
            )

    def test_global_rules_move_to_new_active_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            canonical = INSTALL.contract.GLOBAL_RULES_TEMPLATE.read_bytes()
            (codex_home / "AGENTS.md").write_bytes(b"base\n\n" + canonical)
            (codex_home / "AGENTS.override.md").write_bytes(b"temporary override\n")

            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            self.assertEqual(plan.global_rules_target, codex_home / "AGENTS.override.md")
            INSTALL.apply_plan(plan, global_rules=True)

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
            canonical_lf = INSTALL.contract.GLOBAL_RULES_TEMPLATE.read_bytes().replace(
                b"\r\n", b"\n"
            )
            crlf_template.write_bytes(canonical_lf.replace(b"\n", b"\r\n"))
            original_reader = INSTALL.read_managed_source

            def read_crlf_template(path: Path, label: str, plan):
                if path == crlf_template:
                    return crlf_template.read_bytes()
                return original_reader(path, label, plan)

            with (
                mock.patch.object(INSTALL.contract, "GLOBAL_RULES_TEMPLATE", crlf_template),
                mock.patch.object(INSTALL, "read_managed_source", read_crlf_template),
            ):
                plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, global_rules=True)

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

            plan = self.build(codex_home, skills_root)

            self.assertTrue(any("markers corrupt" in item for item in plan.conflicts))
            with self.assertRaises(RuntimeError):
                INSTALL.apply_plan(plan, global_rules=True)
            self.assertEqual(agents_path.read_bytes(), original)
            self.assertEqual(list(skills_root.iterdir()), [])

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
                global_rules=True,
            )

            self.assertEqual(plan.conflicts, [])
            self.assertFalse(any(operation.path == preferences for operation in plan.operations))

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

            plan = self.build(codex_home, skills_root)

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

            plan = self.build(linked_parent / "codex-home", skills_root)

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

            plan = self.build(codex_home, skills_root)

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

            plan = self.build(junction, skills_root)

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
                plan = self.build(codex_home, skills_root)

            self.assertTrue(
                any("global instructions unreadable" in item for item in plan.conflicts)
            )

    def test_failed_verification_rolls_back_every_completed_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_bytes(b"original\n")
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])

            with (
                mock.patch.object(INSTALL, "verification_failures", return_value=["boom"]),
                self.assertRaises(RuntimeError),
            ):
                INSTALL.apply_plan(plan, global_rules=True)

            self.assertEqual(agents_path.read_bytes(), b"original\n")
            self.assertEqual(list(skills_root.iterdir()), [])
            self.assertFalse((codex_home / "agents").exists())

    def test_write_failure_rolls_back_completed_writes_and_created_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            existing = codex_home / "existing.txt"
            existing.write_bytes(b"old\n")
            created = skills_root / "created-parent" / "created.txt"
            failed = codex_home / "failed-parent" / "failed.txt"
            plan = INSTALL.InstallPlan(codex_home=codex_home, skills_root=skills_root)
            plan.operations.extend(
                (
                    INSTALL.Operation(existing, "update", b"new\n", b"old\n"),
                    INSTALL.Operation(created, "create", b"created\n", None),
                    INSTALL.Operation(failed, "fail", b"failed\n", None),
                )
            )
            real_atomic_write = INSTALL.atomic_write

            def fail_selected_write(path: Path, content: bytes) -> None:
                if path == failed:
                    raise OSError("forced write failure")
                real_atomic_write(path, content)

            with (
                mock.patch.object(INSTALL, "atomic_write", fail_selected_write),
                self.assertRaisesRegex(OSError, "forced write failure"),
            ):
                INSTALL.apply_plan(plan, global_rules=False)

            self.assertEqual(existing.read_bytes(), b"old\n")
            self.assertFalse(created.exists())
            self.assertFalse(created.parent.exists())
            self.assertFalse(failed.parent.exists())

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
            plan.operations.append(INSTALL.Operation(target, "test", b"new\n", b"old\n"))
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
                    INSTALL.apply_plan(plan, global_rules=False)
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
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            agents_path.write_bytes(b"concurrent edit\n")

            with self.assertRaisesRegex(RuntimeError, "changed after planning"):
                INSTALL.apply_plan(plan, global_rules=True)

            self.assertEqual(agents_path.read_bytes(), b"concurrent edit\n")
            self.assertEqual(list(skills_root.iterdir()), [])

    def test_apply_rejects_a_missing_target_that_appears_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            target = codex_home / "agents" / "worker.toml"
            target.parent.mkdir()
            target.write_bytes(b"concurrent user file\n")

            with self.assertRaisesRegex(RuntimeError, "appeared after planning"):
                INSTALL.apply_plan(plan, global_rules=True)

            self.assertEqual(target.read_bytes(), b"concurrent user file\n")
            self.assertEqual(list(skills_root.iterdir()), [])

    def test_apply_rejects_a_parent_link_created_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            external = Path(temporary).resolve() / "external"
            external.mkdir()
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])
            try:
                (skills_root / "codex-orchestration").symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            with self.assertRaisesRegex(RuntimeError, "linked or conflicting"):
                INSTALL.apply_plan(plan, global_rules=True)

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
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, global_rules=True)

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
            plan = self.build(codex_home, skills_root)
            self.assertEqual(plan.conflicts, [])

            INSTALL.apply_plan(plan, global_rules=True)

            installed_attributes = get_attributes(api_path)
            self.assertNotEqual(installed_attributes, invalid_file_attributes)
            self.assertTrue(installed_attributes & file_attribute_hidden)

    def test_windows_extended_paths_cover_drive_and_unc_forms(self) -> None:
        self.assertEqual(
            INSTALL.windows_extended_path(r"C:\runtime\file"),
            r"\\?\C:\runtime\file",
        )
        self.assertEqual(
            INSTALL.windows_extended_path(r"\\server\share\file"),
            r"\\?\UNC\server\share\file",
        )
        self.assertEqual(
            INSTALL.windows_extended_path(r"\\?\C:\runtime\file"),
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
            self.assertIn("Dry run only.", dry_run.stdout)
            self.assertNotIn("Apply this installation plan?", dry_run.stdout)
            self.assertNotIn("Installation cancelled", dry_run.stdout)
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

            missing_language_apply = subprocess.run(
                [*command, "--apply"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                missing_language_apply.returncode,
                2,
                missing_language_apply.stdout + missing_language_apply.stderr,
            )
            self.assertFalse(runtime_root.exists())

    def test_cli_zero_arguments_resolve_documented_noninteractive_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            environment = os.environ.copy()
            environment.pop("CODEX_HOME", None)
            environment["HOME"] = str(home)
            environment["USERPROFILE"] = str(home)

            result = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "install.py")],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(f"Codex home: {home / '.codex'}", result.stdout)
            self.assertIn(f"Skill root: {home / '.codex' / 'skills'}", result.stdout)
            self.assertIn("first install requires --language", result.stdout)
            self.assertFalse((home / ".codex").exists())

    def test_cli_explicit_codex_home_derives_its_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "custom-codex"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_ROOT / "install.py"),
                    "--codex-home",
                    str(codex_home),
                    "--language",
                    "en",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"Codex home: {codex_home}", result.stdout)
            self.assertIn(f"Skill root: {codex_home / 'skills'}", result.stdout)
            self.assertFalse(codex_home.exists())

    def test_interactive_terminal_requires_input_and_output_ttys(self) -> None:
        for stdin_isatty, stdout_isatty, expected in (
            (True, True, True),
            (True, False, False),
            (False, True, False),
            (False, False, False),
        ):
            with self.subTest(stdin=stdin_isatty, stdout=stdout_isatty):
                stdin = mock.Mock()
                stdin.isatty.return_value = stdin_isatty
                stdout = mock.Mock()
                stdout.isatty.return_value = stdout_isatty
                with (
                    mock.patch.object(INSTALL.sys, "stdin", stdin),
                    mock.patch.object(INSTALL.sys, "stdout", stdout),
                ):
                    self.assertEqual(INSTALL.interactive_terminal(), expected)

    def test_zero_argument_interactive_install_uses_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            codex_home = home / ".codex"
            skills_root = codex_home / "skills"
            answers = iter(("", "y"))

            def answer_prompt(prompt: str) -> str:
                print(prompt, end="")
                return next(answers)

            expected_plan = INSTALL.build_plan(
                codex_home,
                skills_root,
                language="zh-CN",
                global_rules=True,
            )
            self.assertEqual(expected_plan.conflicts, [])
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}),
                mock.patch.object(INSTALL, "detected_task_package_language", return_value="zh-CN"),
                mock.patch("builtins.input", side_effect=answer_prompt) as prompt,
                contextlib.redirect_stdout(output),
            ):
                result = INSTALL.main([], interactive=True)

            self.assertEqual(result, 0)
            self.assertEqual(prompt.call_count, 2)
            rendered = output.getvalue()
            self.assertIn("Codex Orchestration installation plan", rendered)
            self.assertIn(f"Codex home: {codex_home}", rendered)
            self.assertIn(f"Skill root: {skills_root}", rendered)
            self.assertIn("CODEX-ORCHESTRATION:GLOBAL-RULES:START", rendered)
            self.assertIn("CODEX-ORCHESTRATION:GLOBAL-RULES:END", rendered)
            self.assertEqual(rendered.count("[CREATE]"), len(expected_plan.operations))
            confirmation_index = rendered.index("Apply this installation plan?")
            for operation in expected_plan.operations:
                operation_line = f"[CREATE] {operation.path} — {operation.reason}"
                digest = f"sha256={INSTALL.sha256_bytes(operation.content)}"
                self.assertLess(rendered.index(operation_line), confirmation_index)
                self.assertLess(rendered.index(digest), confirmation_index)
            self.assertLess(
                rendered.index("Codex Orchestration installation plan"), confirmation_index
            )
            self.assertLess(
                rendered.index("CODEX-ORCHESTRATION:GLOBAL-RULES:END"), confirmation_index
            )
            self.assertTrue((codex_home / "AGENTS.md").is_file())
            self.assertTrue((skills_root / "codex-orchestration" / "SKILL.md").is_file())
            preferences = codex_home / "codex-orchestration" / "preferences.toml"
            self.assertIn(
                'task_package_language = "zh-CN"', preferences.read_text(encoding="utf-8")
            )

            current_output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}),
                mock.patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
                contextlib.redirect_stdout(current_output),
            ):
                current = INSTALL.main([], interactive=True)

            self.assertEqual(current, 0)
            self.assertIn("[CURRENT] no managed runtime changes", current_output.getvalue())
            self.assertIn("OK: managed runtime is already current", current_output.getvalue())

            managed_agent = codex_home / "agents" / "worker.toml"
            managed_agent.write_bytes(b"managed Agent drift\n")
            expected_update = INSTALL.build_plan(
                codex_home,
                skills_root,
                language=None,
                global_rules=True,
            )
            self.assertEqual(expected_update.conflicts, [])
            update_output = io.StringIO()

            def confirm_update(prompt: str) -> str:
                print(prompt, end="")
                return "y"

            with (
                mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}),
                mock.patch("builtins.input", side_effect=confirm_update) as update_prompt,
                contextlib.redirect_stdout(update_output),
            ):
                second = INSTALL.main([], interactive=True)

            self.assertEqual(second, 0)
            self.assertEqual(update_prompt.call_count, 1)
            update_rendered = update_output.getvalue()
            update_confirmation = update_rendered.index("Apply this installation plan?")
            self.assertEqual(update_rendered.count("[UPDATE]"), len(expected_update.operations))
            for operation in expected_update.operations:
                operation_line = f"[UPDATE] {operation.path} — {operation.reason}"
                digest = f"sha256={INSTALL.sha256_bytes(operation.content)}"
                self.assertLess(update_rendered.index(operation_line), update_confirmation)
                self.assertLess(update_rendered.index(digest), update_confirmation)
            self.assertLess(
                update_rendered.index("CODEX-ORCHESTRATION:GLOBAL-RULES:END"),
                update_confirmation,
            )
            self.assertTrue(managed_agent.is_file())
            self.assertIn(
                'task_package_language = "zh-CN"', preferences.read_text(encoding="utf-8")
            )

    def test_interactive_install_can_be_cancelled_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            codex_home.mkdir()
            skills_root.mkdir()
            personal_rules = b"# Personal rules\n"
            (codex_home / "AGENTS.md").write_bytes(personal_rules)
            agents_root = codex_home / "agents"
            agents_root.mkdir()
            (agents_root / "worker.toml").write_bytes(b"user-owned Agent drift\n")
            preferences_root = codex_home / "codex-orchestration"
            preferences_root.mkdir()
            (preferences_root / "preferences.toml").write_text(
                'schema_version = 1\ntask_package_language = "en"\n',
                encoding="utf-8",
            )
            managed_skill = skills_root / "codex-orchestration"
            managed_skill.mkdir()
            (managed_skill / "SKILL.md").write_text(
                "---\nname: codex-orchestration\ndescription: local drift\n---\n",
                encoding="utf-8",
            )
            (skills_root / "user-owned.txt").write_bytes(b"preserve me\n")

            def snapshot(root: Path) -> dict[Path, bytes | None]:
                return {
                    path.relative_to(root): None if path.is_dir() else path.read_bytes()
                    for path in root.rglob("*")
                }

            codex_before = snapshot(codex_home)
            skills_before = snapshot(skills_root)
            output = io.StringIO()
            with (
                mock.patch("builtins.input", return_value="n"),
                contextlib.redirect_stdout(output),
            ):
                result = INSTALL.main(
                    [
                        "--codex-home",
                        str(codex_home),
                        "--skills-root",
                        str(skills_root),
                        "--language",
                        "zh-CN",
                    ],
                    interactive=True,
                )

            self.assertEqual(result, 0)
            self.assertEqual(snapshot(codex_home), codex_before)
            self.assertEqual(snapshot(skills_root), skills_before)
            self.assertIn("Installation cancelled; no files changed.", output.getvalue())

    def test_interactive_apply_skips_plan_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.paths(temporary)
            with (
                mock.patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = INSTALL.main(
                    [
                        "--codex-home",
                        str(codex_home),
                        "--skills-root",
                        str(skills_root),
                        "--language",
                        "en",
                        "--apply",
                    ],
                    interactive=True,
                )

            self.assertEqual(result, 0)
            self.assertTrue((codex_home / "AGENTS.md").is_file())
            self.assertTrue((skills_root / "codex-orchestration" / "SKILL.md").is_file())

    def test_detected_task_package_language_uses_chinese_locale_family(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"LC_ALL": "zh_TW.UTF-8", "LC_MESSAGES": "en_US.UTF-8", "LANG": "en_US.UTF-8"},
        ):
            self.assertEqual(INSTALL.detected_task_package_language(), "zh-CN")

        with (
            mock.patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": ""}),
            mock.patch.object(
                INSTALL.locale,
                "getlocale",
                return_value=("Chinese (Simplified)_China", "936"),
            ),
        ):
            self.assertEqual(INSTALL.detected_task_package_language(), "zh-CN")

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
                "--apply",
            ]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            effective_home = INSTALL.contract.canonical_selected_root(codex_home)
            effective_skills = INSTALL.contract.canonical_selected_root(skills_root)
            self.assertTrue((effective_home / "AGENTS.md").is_file())
            self.assertTrue((effective_skills / "codex-orchestration" / "SKILL.md").is_file())
            self.assertTrue((effective_skills / "codex-review-gate" / "SKILL.md").is_file())
            self.assertFalse((effective_skills / "simplicity-review").exists())
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

            uninstall_dry_run = subprocess.run(
                [*second_command, "--uninstall"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                uninstall_dry_run.returncode,
                0,
                uninstall_dry_run.stdout + uninstall_dry_run.stderr,
            )
            self.assertIn("Codex Orchestration uninstall plan", uninstall_dry_run.stdout)
            self.assertIn("[DELETE]", uninstall_dry_run.stdout)
            self.assertTrue((effective_skills / "codex-orchestration" / "SKILL.md").is_file())

            uninstall = subprocess.run(
                [*second_command, "--uninstall", "--apply"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
            self.assertIn("managed runtime absence verified", uninstall.stdout)
            self.assertFalse((effective_skills / "codex-orchestration" / "SKILL.md").exists())
            self.assertNotIn(
                INSTALL.contract.GLOBAL_RULES_START,
                (effective_home / "AGENTS.md").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
