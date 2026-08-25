from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
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
        temporary_path = temporary_path.resolve()
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

    def test_worktree_roots_are_peer_tasks_with_integrated_review(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (ROOT / "references" / "worktree-roots.md").read_text(encoding="utf-8")
        global_rules = (ROOT / "examples" / "global-agents-block.md").read_text(encoding="utf-8")
        normalized_contract = re.sub(r"\s+", " ", contract)

        self.assertIn("independent task and session", skill)
        self.assertIn("It is a peer root task, not a derived writable agent", normalized_contract)
        self.assertIn("at most three nonterminal Worktree Roots", normalized_contract)
        self.assertIn("at most eight spawned-agent threads", contract)
        self.assertIn("same `explorer`, reviewer, worker, and specialist roles", contract)
        self.assertIn("batch roles, not different agent types", contract)
        self.assertIn("distinct official worktree", contract)
        self.assertIn("failed or canceled lane blocks successful delivery", contract)
        self.assertIn("Stop convergence", contract)
        self.assertIn("Lane review never substitutes for the integrated review", contract)
        self.assertIn(
            "Loads `codex-review-gate`, then selects and completes its R0-R3 review gate against "
            "the combined diff",
            contract,
        )
        self.assertIn(
            "neither the Integration Root nor its local workers write the repository",
            global_rules,
        )
        self.assertFalse((ROOT / "agents" / "worktree-root.toml").exists())

    def test_delivery_review_is_independent_from_delegation_admission(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        review = (ROOT / "skills" / "codex-review-gate" / "SKILL.md").read_text(encoding="utf-8")
        global_rules = (ROOT / "examples" / "global-agents-block.md").read_text(encoding="utf-8")

        self.assertIsNone(
            re.search(r"^#{1,6}\s+Review gate\b.*$", skill, re.IGNORECASE | re.MULTILINE)
        )
        self.assertIn("`codex-review-gate` defines the review route", skill)
        self.assertIn("delivery control, not an admission test", review)
        self.assertIn("current user message does not need to name a subagent", review)
        self.assertIn("Choose the highest matching level", review)
        self.assertIn("Changed line or file counts never determine a level", review)
        self.assertIn(
            "This includes local runtime, test-semantic, dependency, or build changes", review
        )
        self.assertIn("repository implementation, tests, dependencies", review)
        self.assertIn("This fail-closed fallback", review)
        self.assertIn("## Code review", global_rules)
        self.assertIn("repository implementation, tests, dependencies", global_rules)
        self.assertIn("This rule authorizes only those Reviewer calls", global_rules)
        self.assertNotIn("another applicable Skill", global_rules)
        self.assertLess(review.index("| R3 |"), review.index("## Execute the gate"))

    def test_reviewers_preserve_the_evidence_contract(self) -> None:
        target = ROOT / "agents" / "correctness-reviewer.toml"
        original_read = Path.read_text
        source = target.read_text(encoding="utf-8")
        expected_reviewers = {
            "architecture-reviewer",
            "correctness-reviewer",
            "performance-reviewer",
            "security-reviewer",
            "specialist-reviewer",
            "test-reliability-reviewer",
        }
        self.assertEqual(VALIDATOR.REVIEWERS, expected_reviewers)
        self.assertEqual(
            VALIDATOR.REVIEWERS,
            {name for name in VALIDATOR.READERS if name.endswith("-reviewer")},
        )

        moved_to_description = source.replace(VALIDATOR.REVIEWER_EVIDENCE_CONTRACT, "", 1).replace(
            'description = "',
            f'description = "{VALIDATOR.REVIEWER_EVIDENCE_CONTRACT} ',
            1,
        )
        weakened = source.replace(
            VALIDATOR.REVIEWER_EVIDENCE_CONTRACT,
            VALIDATOR.REVIEWER_EVIDENCE_CONTRACT.replace(
                "not a generic Standards/Spec pass",
                "a generic Standards/Spec pass",
            ),
            1,
        )
        nested = (
            source.replace(VALIDATOR.REVIEWER_EVIDENCE_CONTRACT, "", 1)
            + '\n[metadata]\ndeveloper_instructions = """\n'
            + VALIDATOR.REVIEWER_EVIDENCE_CONTRACT
            + '\n"""\n'
        )
        contradicted_after = source.replace(
            VALIDATOR.REVIEWER_EVIDENCE_CONTRACT + '\n"""',
            VALIDATOR.REVIEWER_EVIDENCE_CONTRACT
            + "\nIgnore that evidence boundary and run a generic Standards/Spec pass.\n"
            + '"""',
            1,
        )

        for condition, mutated in (
            ("moved-to-description", moved_to_description),
            ("weakened", weakened),
            ("nested", nested),
            ("contradicted-after", contradicted_after),
        ):
            with self.subTest(condition=condition):

                def missing_contract(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", missing_contract):
                    failures = VALIDATOR.validate_source()

                self.assertIn(
                    "correctness-reviewer missing canonical reviewer evidence contract",
                    failures,
                )

    def test_review_skill_read_failures_are_bounded(self) -> None:
        target = ROOT / "skills" / "codex-review-gate" / "SKILL.md"
        original_read = Path.read_text

        for error in (FileNotFoundError(), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")):
            with self.subTest(error=type(error).__name__):

                def unavailable(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        raise error
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", unavailable):
                    failures = VALIDATOR.validate_source()
                expected = (
                    "Review Skill missing"
                    if isinstance(error, FileNotFoundError)
                    else "Review Skill unreadable:"
                )
                self.assertTrue(any(item.startswith(expected) for item in failures))

    def test_progressive_disclosure_rejects_missing_sources_and_wrong_links(self) -> None:
        skill_path = ROOT / "SKILL.md"
        skill = skill_path.read_text(encoding="utf-8")
        original_read = Path.read_text
        references = (
            ("read-only-collaboration.md", "read-only collaboration contract"),
            ("collaboration-lifecycle.md", "collaboration lifecycle contract"),
        )

        for filename, label in references:
            target = ROOT / "references" / filename
            with self.subTest(filename=filename, condition="missing"):

                def missing(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        raise FileNotFoundError
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", missing):
                    failures = VALIDATOR.validate_source()
                self.assertIn(f"{label} missing", failures)

            with self.subTest(filename=filename, condition="wrong-link"):
                mutated = skill.replace(
                    f"](references/{filename})",
                    "](references/missing.md)",
                    1,
                )

                def wrong_link(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == skill_path:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", wrong_link):
                    failures = VALIDATOR.validate_source()
                self.assertTrue(
                    any(item.startswith("missing Skill reference pointer:") for item in failures)
                )

    def test_orchestration_skill_cannot_redefine_review_gate(self) -> None:
        skill_path = ROOT / "SKILL.md"
        original_read = Path.read_text
        skill = skill_path.read_text(encoding="utf-8")
        for heading in (
            "##  review GATE",
            "### Review gate policy",
            "#### REVIEW GATE <!-- duplicate -->",
        ):
            with self.subTest(heading=heading):
                mutated = skill + f"\n{heading}\n\nDuplicate.\n"

                def duplicate_gate(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == skill_path:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", duplicate_gate):
                    failures = VALIDATOR.validate_source()
                self.assertIn("orchestration Skill must not redefine the Review gate", failures)

    def test_worktree_contract_rejects_limit_and_sequence_drift(self) -> None:
        contract = (ROOT / "references" / "worktree-roots.md").read_text(encoding="utf-8")
        self.assertEqual(VALIDATOR.worktree_contract_failures(contract), [])

        mutations = (
            (
                "independent Codex task and session",
                "derived Codex task and session",
            ),
            (
                "at most three nonterminal Worktree Roots",
                "at most four nonterminal Worktree Roots",
            ),
            (
                "at most eight spawned-agent threads",
                "at most nine spawned-agent threads",
            ),
            (
                "fails closed and does not spawn",
                "warns and continues to spawn",
            ),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                mutated = contract.replace(old, new, 1)
                self.assertTrue(VALIDATOR.worktree_contract_failures(mutated))

        first, second, *_ = VALIDATOR.WORKTREE_INTEGRATION_SEQUENCE
        reordered = contract.replace(first, "__FIRST__", 1)
        reordered = reordered.replace(second, first, 1).replace("__FIRST__", second, 1)
        self.assertIn(
            "worktree-root integration sequence must be complete batch, serial merge, "
            "combined validation, then R0-R3 review",
            VALIDATOR.worktree_contract_failures(reordered),
        )
        for marker in VALIDATOR.WORKTREE_INTEGRATION_SEQUENCE:
            with self.subTest(missing_marker=marker):
                missing = contract.replace(marker, "", 1)
                self.assertIn(
                    f"worktree-root integration step missing: {marker}",
                    VALIDATOR.worktree_contract_failures(missing),
                )

        self.assertTrue(VALIDATOR.worktree_contract_failures("   \n"))

    def test_worktree_contract_missing_path_has_actionable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            failures: list[str] = []
            source = VALIDATOR.read_required_text(
                Path(temporary_directory) / "worktree-roots.md",
                "worktree-root contract",
                failures,
            )
        self.assertEqual(source, "")
        self.assertEqual(failures, ["worktree-root contract missing"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "worktree-roots.md"
            invalid_path.write_bytes(b"\xff")
            failures = []
            source = VALIDATOR.read_required_text(
                invalid_path,
                "worktree-root contract",
                failures,
            )
        self.assertEqual(source, "")
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("worktree-root contract unreadable:"))

    def test_public_source_scan_reports_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid.md"
            invalid_path.write_bytes(b"\xff")
            with mock.patch.object(VALIDATOR, "public_text_files", return_value=[invalid_path]):
                failures = VALIDATOR.validate_source()
        self.assertTrue(
            any(
                failure.startswith("public source ") and " unreadable:" in failure
                for failure in failures
            )
        )

    def test_worktree_adr_decisions_are_validated(self) -> None:
        adr = (ROOT / "docs" / "adr" / "0009-coordinate-independent-worktree-roots.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(VALIDATOR.worktree_adr_failures(adr), [])
        normalized_adr = " ".join(adr.split())
        mutated = normalized_adr.replace("Failed or canceled lanes", "Incomplete lanes", 1)
        self.assertIn(
            "worktree-root ADR missing decision: Failed or canceled lanes",
            VALIDATOR.worktree_adr_failures(mutated),
        )
        too_many = normalized_adr.replace("at most three", "at most four", 1)
        self.assertIn(
            "worktree-root ADR missing decision: at most three nonterminal Worktree Roots",
            VALIDATOR.worktree_adr_failures(too_many),
        )
        first, second, *_ = VALIDATOR.WORKTREE_ADR_SEQUENCE
        reordered = normalized_adr.replace(first, "__FIRST__", 1)
        reordered = reordered.replace(second, first, 1).replace("__FIRST__", second, 1)
        self.assertIn(
            "worktree-root ADR sequence must be accepted batch, serial merge, combined "
            "validation, then final R0-R3 review",
            VALIDATOR.worktree_adr_failures(reordered),
        )
        self.assertTrue(VALIDATOR.worktree_adr_failures("\n"))

    def test_skill_frontmatter_version_matches_project_metadata(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        review_skill = (ROOT / "skills" / "codex-review-gate" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(VALIDATOR.source_version_failures(project, skill), [])
        self.assertEqual(VALIDATOR.source_version_failures(project, review_skill), [])

        project_version = VALIDATOR.top_level_values(project)["version"]
        mutated = skill.replace(f"version: {project_version}", "version: 0.8.0", 1)
        mutated += f"\nversion: {project_version}\n"
        self.assertIn(
            "Skill front matter version must match project version",
            VALIDATOR.source_version_failures(project, mutated),
        )

        duplicate = skill.replace(
            f"  version: {project_version}",
            f"  version: {project_version}\n  version: {project_version}",
            1,
        )
        self.assertIn(
            "Skill front matter version must appear exactly once",
            VALIDATOR.source_version_failures(project, duplicate),
        )

        duplicate_project = project.replace(
            f'version = "{project_version}"',
            f'version = "0.8.0"\nversion = "{project_version}"',
            1,
        )
        self.assertIn(
            "project version must appear exactly once",
            VALIDATOR.source_version_failures(duplicate_project, skill),
        )

    def test_v2_policy_does_not_use_a_main_agent_route_hook(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        lifecycle = (ROOT / "references" / "collaboration-lifecycle.md").read_text(encoding="utf-8")
        self.assertFalse((ROOT / "hooks" / "orchestration_route.py").exists())
        self.assertIn('fork_turns="none"', skill)
        self.assertIn("collaboration-tool schemas are the sole authority", skill)
        self.assertIn("earlier final notification", lifecycle)
        self.assertNotIn("functions.exec", skill)

    def test_only_panel_routing_uses_host_model_binding(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        routing = (ROOT / "references" / "model-routing.md").read_text(encoding="utf-8")
        collaboration = (ROOT / "references" / "read-only-collaboration.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("references/read-only-collaboration.md", skill)
        self.assertIn("Only `panel` and the panel workstream in `hybrid`", routing)
        self.assertIn(
            "hybrid specialist delegation never inspect the parent\nmodel identity", routing
        )
        self.assertIn("latest host-generated system or developer model binding", routing)
        self.assertIn("explicit `model_switch`", routing)
        self.assertIn("uses `panel_routes.gpt`", routing)
        self.assertIn("uses `panel_routes.third_party`", routing)
        self.assertIn("fails closed to `panel_routes.gpt`", routing)
        self.assertIn("Specialist workstreams use ordinary role routes", routing)
        self.assertIn(
            "semantic instructions, not required labels",
            re.sub(r"\s+", " ", collaboration),
        )
        self.assertIn("brief makes\nthe workstream clear", routing)
        self.assertNotIn("WORKSTREAM: panel | specialist", skill)

    def test_routing_example_schema_validates_panel_and_service_requirements(self) -> None:
        source = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")
        self.assertEqual(VALIDATOR.routing_example_failures(source), [])

        missing_service = source.replace('service_tier = "SERVICE_TIER"\n', "", 1)
        self.assertTrue(
            any(
                "missing required fields" in failure
                for failure in VALIDATOR.routing_example_failures(missing_service)
            )
        )

        invalid_service = source.replace('service_tier = "SERVICE_TIER"', 'service_tier = "fast"')
        self.assertIn(
            "model routing has an invalid service_tier",
            VALIDATOR.routing_example_failures(invalid_service),
        )

        invalid_phase = source.replace('phase = "primary"', 'phase = "reserve"', 1)
        self.assertTrue(
            any(
                "invalid phase" in failure
                for failure in VALIDATOR.routing_example_failures(invalid_phase)
            )
        )

        unknown_family = source.replace("panel_routes.gpt", "panel_routes.unknown")
        self.assertIn(
            "model routing panel families are invalid",
            VALIDATOR.routing_example_failures(unknown_family),
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

    def test_model_routing_rejects_invalid_types_and_weak_panels(self) -> None:
        source = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")

        cases = {
            "float schema": source.replace("schema_version = 2", "schema_version = 2.0"),
            "invalid task kind": source.replace('task_kind = "TASK_KIND"', "task_kind = []"),
            "unhashable phase": source.replace('phase = "primary"', "phase = []", 1),
            "unhashable tier": source.replace(
                'service_tier = "SERVICE_TIER"', "service_tier = []", 1
            ),
            "duplicate panel model": source.replace(
                'model = "MODEL_ID_PRIMARY_2"', 'model = "MODEL_ID_PRIMARY_1"', 1
            ),
            "one primary": source.replace(
                '[[panel_routes.gpt]]\nphase = "primary"\nmodel = "MODEL_ID_PRIMARY_2"',
                '[[panel_routes.gpt]]\nphase = "fallback"\nmodel = "MODEL_ID_PRIMARY_2"',
                1,
            ),
        }
        for label, candidate in cases.items():
            with self.subTest(label=label):
                self.assertTrue(VALIDATOR.routing_example_failures(candidate))

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

        single_quoted = source.replace('"LANGUAGE"', "'zh-CN'")
        self.assertEqual(
            VALIDATOR.top_level_values(single_quoted).get("task_package_language"),
            "zh-CN",
        )

        unsupported = source.replace('"LANGUAGE"', '"fr"')
        self.assertIn(
            "preferences task_package_language is invalid",
            VALIDATOR.preferences_failures(unsupported),
        )

    def test_worker_profiles_accept_natural_briefs_without_scope_hook(self) -> None:
        self.assertFalse(os.path.lexists(ROOT / "hooks" / "subagent_scope.py"))
        for name in VALIDATOR.WRITERS:
            source = (ROOT / "agents" / f"{name}.toml").read_text(encoding="utf-8")
            self.assertIn("labels and fixed fields are not required", source)
            self.assertIn("necessary adjacent files", source)
            self.assertNotIn("WRITE LEASE: granted", source)
            self.assertNotIn("ALLOWED PATHS", source)

    def test_source_contract_rejects_broken_retired_hook_symlink(self) -> None:
        target = ROOT / "hooks" / "subagent_scope.py"
        original_lexists = os.path.lexists

        def fake_lexists(path: str | Path) -> bool:
            return Path(path) == target or original_lexists(path)

        with mock.patch.object(VALIDATOR.os.path, "lexists", side_effect=fake_lexists):
            failures = VALIDATOR.validate_source()

        self.assertTrue(any("retired lifecycle Hook remains" in item for item in failures))

    def test_runtime_validation_accepts_copied_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

    def test_global_rules_validation_follows_codex_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            canonical = VALIDATOR.GLOBAL_RULES_TEMPLATE.read_bytes()
            base = codex_home / "AGENTS.md"
            override = codex_home / "AGENTS.override.md"
            base.write_bytes(b"base\n\n" + canonical)
            self.assertEqual(VALIDATOR.validate_global_rules(codex_home), [])

            override.write_bytes(b"override\n")
            failures = VALIDATOR.validate_global_rules(codex_home)
            self.assertTrue(
                any(
                    "inactive global instructions retain managed block" in item for item in failures
                )
            )
            self.assertTrue(any("global rules block missing" in item for item in failures))

            base.write_bytes(b"base\n")
            override.write_bytes(b"override\n\n" + canonical)
            self.assertEqual(VALIDATOR.validate_global_rules(codex_home), [])

    def test_global_rules_validation_rejects_corrupt_or_duplicate_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            target = codex_home / "AGENTS.md"
            target.write_bytes(VALIDATOR.GLOBAL_RULES_START + b"\nmissing end\n")
            self.assertTrue(
                any(
                    "markers corrupt or duplicated" in item
                    for item in VALIDATOR.validate_global_rules(codex_home)
                )
            )

            canonical = VALIDATOR.GLOBAL_RULES_TEMPLATE.read_bytes()
            target.write_bytes(
                canonical + b"\n# mention " + VALIDATOR.GLOBAL_RULES_END + b" token\n"
            )
            self.assertTrue(
                any(
                    "markers corrupt or duplicated" in item
                    for item in VALIDATOR.validate_global_rules(codex_home)
                )
            )

            target.write_bytes(canonical + b"\n" + canonical)
            self.assertTrue(
                any(
                    "markers corrupt or duplicated" in item
                    for item in VALIDATOR.validate_global_rules(codex_home)
                )
            )

    def test_runtime_validation_checks_saved_task_package_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
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

    def test_runtime_validation_checks_saved_model_routing(self) -> None:
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
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            routing_path = codex_home / "codex-orchestration" / "model-routing.toml"
            routing_path.parent.mkdir()
            routing_path.write_text(route, encoding="utf-8")
            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

            routing_path.write_text(
                route.replace("schema_version = 2", "schema_version = 2.0"),
                encoding="utf-8",
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("runtime model routing invalid" in item for item in failures))

    def test_runtime_validation_reports_missing_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary).resolve()
            failures = VALIDATOR.validate_runtime(
                temporary_path / "codex-home", temporary_path / "skills"
            )

        self.assertTrue(any("runtime Skill missing" in failure for failure in failures))
        self.assertTrue(any("runtime Agent directory missing" in failure for failure in failures))

    def test_runtime_validation_reports_main_skill_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            (skills_root / "codex-orchestration" / "SKILL.md").write_text(
                "drift\n", encoding="utf-8"
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("runtime Skill file differs" in failure for failure in failures))

    def test_runtime_validation_reports_missing_progressive_disclosure_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            target = (
                skills_root / "codex-orchestration" / "references" / "collaboration-lifecycle.md"
            )
            target.unlink()
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(
            any(
                "runtime Skill file differs" in failure and "collaboration-lifecycle.md" in failure
                for failure in failures
            )
        )

    def test_runtime_validation_rejects_method_skill_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            (skills_root / "prototype" / "SKILL.md").write_text(
                "---\nname: prototype\n---\n", encoding="utf-8"
            )
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("prototype" in failure for failure in failures))

    def test_runtime_validation_rejects_linked_skill_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary).resolve()
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
            temporary_path = Path(temporary).resolve()
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

        self.assertTrue(any("linked" in failure for failure in skill_failures))
        self.assertTrue(any("linked" in failure for failure in home_failures))

    def test_runtime_validation_preserves_unrelated_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "custom_hook.py").write_text("custom\n", encoding="utf-8")

            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

    def test_runtime_validation_rejects_retired_scope_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            target = hooks_root / "subagent_scope.py"
            target.write_text("retired scope\n", encoding="utf-8")
            command = VALIDATOR.expected_hook_command(target, windows=VALIDATOR.os.name == "nt")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SubagentStart": [{"hooks": [{"type": "command", "command": command}]}]
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("subagent_scope.py" in failure for failure in failures))

    def test_runtime_validation_rejects_retired_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary).resolve()
            codex_home, skills_root = self.copy_runtime(temporary_path)
            external_guard = temporary_path / "old-codex" / "hooks" / "subagent_guard.py"
            external_guard.parent.mkdir(parents=True)
            external_guard.write_text("retired\n", encoding="utf-8")
            retired_command = VALIDATOR.expected_hook_command(
                external_guard, windows=VALIDATOR.os.name == "nt"
            )
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
                                            "command": retired_command,
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

    def test_retired_scan_rejects_legacy_guard_variants(self) -> None:
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
                    temporary_path = Path(temporary).resolve()
                    codex_home = temporary_path / "codex-home"
                    hooks_root = codex_home / "hooks"
                    hooks_root.mkdir(parents=True)
                    hooks: dict[str, list[dict[str, object]]] = {}
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

                    failures = VALIDATOR.retired_hook_failures(codex_home, windows=windows)

                self.assertTrue(
                    any(
                        "retired v1-shaped hook registration remains" in failure
                        for failure in failures
                    )
                )

    def test_hook_validation_rejects_retired_guard_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            retired_target = hooks_root / "subagent_guard.py"
            retired_target.write_text("retired\n", encoding="utf-8")

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired Hook path ownership conflicts" in failure for failure in failures)
        )

    def test_retired_scan_accepts_unhashable_foreign_matchers(self) -> None:
        for matcher in ([], {}):
            with self.subTest(matcher=matcher), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary).resolve() / "codex-home"
                codex_home.mkdir()
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": {"PostToolUse": [{"matcher": matcher, "hooks": []}]}}),
                    encoding="utf-8",
                )

                failures = VALIDATOR.retired_hook_failures(codex_home)

            self.assertEqual(failures, [])

    def test_retired_scan_reports_unreadable_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            (hooks_root / "subagent_guard.py").write_text("retired\n", encoding="utf-8")
            with mock.patch.object(VALIDATOR, "file_sha256", side_effect=PermissionError("denied")):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired Hook path unreadable" in failure for failure in failures))

    def test_retired_scan_rejects_dangling_custom_reference_to_managed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            retired_target = hooks_root / "subagent_guard.py"
            command = VALIDATOR.expected_hook_command(
                retired_target, windows=VALIDATOR.os.name == "nt"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired managed Hook registration remains" in failure for failure in failures)
        )

    def test_retired_scan_rejects_parent_traversal_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            (hooks_root / "x").mkdir(parents=True)
            traversal_target = hooks_root / "x" / ".." / "subagent_guard.py"
            command = VALIDATOR.expected_hook_command(
                traversal_target, windows=VALIDATOR.os.name == "nt"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired-looking Hook registration has unsafe path" in item for item in failures)
        )

    def test_retired_scan_rejects_macos_case_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            case_alias = hooks_root / "SUBAGENT_GUARD.PY"
            command = VALIDATOR.expected_hook_command(case_alias, windows=VALIDATOR.os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )

            with mock.patch.object(VALIDATOR.sys, "platform", "darwin"):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired managed Hook registration remains" in item for item in failures)
        )

    def test_retired_scan_rejects_orphan_hardlink_with_retired_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            alias = hooks_root / "custom_alias.py"
            alias.write_bytes(b"known retired fixture\n")
            command = VALIDATOR.expected_hook_command(alias, windows=VALIDATOR.os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"SessionStart": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired project Hook code registration remains" in item for item in failures)
        )

    def test_retired_hash_scan_follows_an_exact_script_symlink_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "renamed_retired_copy.py"
            target.write_bytes(b"known retired fixture\n")
            alias = root / "custom_alias.py"
            try:
                alias.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_guard.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                retired = VALIDATOR.referenced_script_has_retired_hash(
                    alias, windows=VALIDATOR.os.name == "nt"
                )

        self.assertTrue(retired)

    def test_project_hook_path_ambiguity_checks_platform_syntax(self) -> None:
        self.assertTrue(VALIDATOR.hook_path_is_ambiguous("hooks/subagent_guard.py", windows=False))
        self.assertTrue(VALIDATOR.hook_path_is_ambiguous("/$HOME/subagent_guard.py", windows=False))
        self.assertTrue(
            VALIDATOR.hook_path_is_ambiguous("/runtime/hook*/subagent_guard.py", windows=False)
        )
        self.assertTrue(
            VALIDATOR.hook_path_is_ambiguous(
                r"C:\Accounts\%USERNAME%\subagent_guard.py", windows=True
            )
        )
        self.assertFalse(
            VALIDATOR.hook_path_is_ambiguous("/external/subagent_guard.py", windows=False)
        )

    def test_python_invoked_script_accepts_options_without_weakening_exact_parser(self) -> None:
        target = Path("runtime") / "subagent_guard.py"
        arguments = [sys.executable, "-u", str(target)]
        command = (
            " ".join(f'"{argument}"' for argument in arguments)
            if VALIDATOR.os.name == "nt"
            else shlex.join(arguments)
        )

        self.assertIsNone(VALIDATOR.python_hook_script(command, windows=VALIDATOR.os.name == "nt"))
        self.assertEqual(
            VALIDATOR.python_invoked_script(command, windows=VALIDATOR.os.name == "nt"),
            str(target),
        )

    @unittest.skipIf(VALIDATOR.os.name == "nt", "POSIX command syntax only")
    def test_python_invoked_script_accepts_environment_wrappers(self) -> None:
        target = Path("/runtime/hooks/subagent_guard.py")
        direct = f"PYTHONUNBUFFERED=1 {shlex.join([sys.executable, str(target)])}"
        via_env = shlex.join(
            ["/usr/bin/env", "PYTHONUNBUFFERED=1", sys.executable, "-u", str(target)]
        )

        self.assertEqual(
            VALIDATOR.python_invoked_script(direct, windows=False),
            str(target),
        )
        self.assertEqual(
            VALIDATOR.python_invoked_script(via_env, windows=False),
            str(target),
        )

    def test_retired_scan_recognizes_windows_guard_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
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

    def test_runtime_validation_rejects_legacy_v1_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "orchestration_route.py").write_text("legacy\n", encoding="utf-8")
            legacy_digest = next(iter(VALIDATOR.LEGACY_V1_ROUTE_SHA256))
            with mock.patch.object(VALIDATOR, "file_sha256", return_value=legacy_digest):
                failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("retired managed route remains" in failure for failure in failures))

    def test_retired_scan_rejects_conflicting_route_paths(self) -> None:
        for kind in ("foreign", "directory", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary).resolve() / "codex-home"
                hooks_root = codex_home / "hooks"
                hooks_root.mkdir(parents=True)
                route_target = hooks_root / "orchestration_route.py"
                if kind == "foreign":
                    route_target.write_text("foreign\n", encoding="utf-8")
                elif kind == "directory":
                    route_target.mkdir()
                else:
                    external = Path(temporary).resolve() / "external-route.py"
                    external.write_text("external\n", encoding="utf-8")
                    try:
                        route_target.symlink_to(external)
                    except OSError as error:
                        self.skipTest(f"symlinks unavailable: {error}")

                failures = VALIDATOR.retired_hook_failures(codex_home)

            self.assertTrue(any("retired route path" in failure for failure in failures))

    def test_retired_scan_rejects_known_prior_v2_route_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            route_target = hooks_root / "orchestration_route.py"
            route_target.write_text("known prior v2\n", encoding="utf-8")
            original_digest = VALIDATOR.file_sha256
            prior_digest = next(iter(VALIDATOR.KNOWN_PRIOR_V2_ROUTE_SHA256))

            def route_digest(path: Path) -> str:
                return prior_digest if path == route_target else original_digest(path)

            with mock.patch.object(VALIDATOR, "file_sha256", side_effect=route_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired managed route remains" in item for item in failures))

    def test_retired_scan_rejects_external_route_registration_as_ownership_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary).resolve()
            codex_home = temporary_path / "codex-home"
            codex_home.mkdir()
            external_route = temporary_path / "old-codex" / "hooks" / "orchestration_route.py"
            external_route.parent.mkdir(parents=True)
            external_route.write_text("legacy\n", encoding="utf-8")
            route_command = VALIDATOR.expected_hook_command(
                external_route, windows=VALIDATOR.os.name == "nt"
            )
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": route_command,
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
            any("retired route registration ownership conflicts" in item for item in failures)
        )

    def test_retired_scan_preserves_external_route_with_custom_matcher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            external_route = root / "user" / "orchestration_route.py"
            external_route.parent.mkdir()
            external_route.write_text("user route\n", encoding="utf-8")
            command = VALIDATOR.expected_hook_command(
                external_route, windows=VALIDATOR.os.name == "nt"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {"hooks": {"UserPromptSubmit": [{"matcher": "custom", "hooks": [handler]}]}}
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertEqual(failures, [])

    def test_retired_scan_rejects_external_scope_registration_as_ownership_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            external_scope = root / "user" / "subagent_scope.py"
            external_scope.parent.mkdir()
            external_scope.write_text("user copy\n", encoding="utf-8")
            command = VALIDATOR.expected_hook_command(
                external_scope, windows=VALIDATOR.os.name == "nt"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SubagentStart": [{"hooks": [handler]}]}}),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired scope registration ownership conflicts" in item for item in failures)
        )

    def test_retired_scan_checks_guard_and_route_shapes_with_wrong_handler_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            external_guard = root / "user" / "subagent_guard.py"
            external_route = root / "user" / "orchestration_route.py"
            external_guard.parent.mkdir()
            external_guard.write_text("user guard\n", encoding="utf-8")
            external_route.write_text("user route\n", encoding="utf-8")
            windows = VALIDATOR.os.name == "nt"
            guard_handler = {
                "type": "shell",
                "command": VALIDATOR.expected_hook_command(external_guard, windows=windows),
            }
            route_handler = {
                "type": "shell",
                "command": VALIDATOR.expected_hook_command(external_route, windows=windows),
            }
            if windows:
                guard_handler["commandWindows"] = guard_handler["command"]
                route_handler["commandWindows"] = route_handler["command"]
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [{"matcher": r"send_input$", "hooks": [guard_handler]}],
                            "UserPromptSubmit": [{"hooks": [route_handler]}],
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired v1-shaped hook registration" in item for item in failures))
        self.assertTrue(any("retired route registration ownership" in item for item in failures))

    def test_retired_scan_rejects_missing_route_registration_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            missing_route = Path(temporary).resolve() / "old" / "orchestration_route.py"
            route_command = VALIDATOR.expected_hook_command(
                missing_route, windows=VALIDATOR.os.name == "nt"
            )
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": route_command,
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
            any("retired route registration ownership conflicts" in failure for failure in failures)
        )

    def test_retired_scan_preserves_unrelated_hook_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
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
            temporary_path = Path(temporary).resolve()
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

    def test_runtime_cli_validates_global_rules_without_project_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            (codex_home / "AGENTS.md").write_bytes(VALIDATOR.GLOBAL_RULES_TEMPLATE.read_bytes())

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--runtime",
                    "--codex-home",
                    str(codex_home),
                    "--skills-root",
                    str(skills_root),
                    "--global-rules",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: runtime skill and agents match source", result.stdout)

    def test_expected_hook_command_uses_platform_quoting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve() / "hook scripts" / "route.py"
            windows_command = VALIDATOR.expected_hook_command(target, windows=True)
            posix_command = VALIDATOR.expected_hook_command(target, windows=False)

        self.assertNotEqual(windows_command, posix_command)
        self.assertEqual(
            windows_command,
            " ".join(
                f'"{argument}"'
                for argument in (str(Path(sys.executable).absolute()), str(target.absolute()))
            ),
        )
        self.assertTrue(windows_command.startswith('"'))
        self.assertIn(f'"{target.absolute()}"', windows_command)
        self.assertIn(f"'{target.absolute()}'", posix_command)
        self.assertEqual(
            VALIDATOR.python_hook_script(windows_command, windows=True),
            str(target.absolute()),
        )
        self.assertEqual(
            VALIDATOR.python_hook_script(posix_command, windows=False),
            str(target.absolute()),
        )

    def test_retired_scan_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir(parents=True)
            (codex_home / "hooks.json").write_text("{invalid", encoding="utf-8")

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("hooks config invalid" in failure for failure in failures))

    def test_retired_scan_rejects_non_list_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            target = codex_home / "hooks" / "subagent_scope.py"
            command = VALIDATOR.expected_hook_command(target, windows=VALIDATOR.os.name == "nt")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SubagentStart": {"hooks": [{"type": "command", "command": command}]}
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("event must be a list: SubagentStart" in item for item in failures))

    def test_retired_scan_rejects_non_list_group_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            target = codex_home / "hooks" / "subagent_scope.py"
            command = VALIDATOR.expected_hook_command(target, windows=VALIDATOR.os.name == "nt")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SubagentStart": [{"hooks": {"type": "command", "command": command}}]
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("group hooks must be a list" in item for item in failures))

    def test_retired_scan_rejects_shell_operator_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            retired = root / "old" / "subagent_scope.py"
            retired.parent.mkdir()
            retired.write_bytes(b"known retired scope fixture\n")
            windows = VALIDATOR.os.name == "nt"
            separator = "&" if windows else ";"
            command = (
                f"{VALIDATOR.expected_hook_command(retired, windows=windows)} {separator} echo x"
            )
            handler: dict[str, object] = {"type": "command", "command": command}
            if windows:
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": [handler]}]}}),
                encoding="utf-8",
            )
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_scope.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired project Hook code" in item for item in failures))

    def test_retired_scan_rejects_grouped_command_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            retired = root / "old" / "subagent_scope.py"
            retired.parent.mkdir()
            retired.write_bytes(b"known retired scope fixture\n")
            windows = VALIDATOR.os.name == "nt"
            command = f"({VALIDATOR.expected_hook_command(retired, windows=windows)})"
            handler: dict[str, object] = {"type": "command", "command": command}
            if windows:
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": [handler]}]}}),
                encoding="utf-8",
            )
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_scope.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired project Hook code" in item for item in failures))

    @unittest.skipIf(VALIDATOR.os.name == "nt", "POSIX line-continuation syntax only")
    def test_retired_scan_rejects_unparseable_retired_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            retired = root / "old" / "subagent_scope.py"
            retired.parent.mkdir()
            retired.write_bytes(b"known retired scope fixture\n")
            command = f"{VALIDATOR.expected_hook_command(retired, windows=False)}\\"
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [{"hooks": [{"type": "command", "command": command}]}]
                        }
                    }
                ),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("unparseable command" in item for item in failures))

    @unittest.skipIf(VALIDATOR.os.name == "nt", "POSIX line-continuation syntax only")
    def test_retired_scan_rejects_line_continuation_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            retired = root / "old" / "subagent_scope.py"
            retired.parent.mkdir()
            retired.write_bytes(b"known retired scope fixture\n")
            command = VALIDATOR.expected_hook_command(retired, windows=False).replace(
                "subagent_scope.py", "subagent_\\\nscope.py"
            )
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [{"hooks": [{"type": "command", "command": command}]}]
                        }
                    }
                ),
                encoding="utf-8",
            )
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_scope.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired project Hook code" in item for item in failures))

    def test_retired_scan_rejects_nul_in_project_hook_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            target = Path(f"{codex_home / 'hooks' / 'subagent_scope.py'}\0")
            command = VALIDATOR.expected_hook_command(target, windows=VALIDATOR.os.name == "nt")
            handler: dict[str, object] = {"type": "command", "command": command}
            if VALIDATOR.os.name == "nt":
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SubagentStart": [{"hooks": [handler]}]}}),
                encoding="utf-8",
            )

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(
            any("retired-looking Hook registration has unsafe path" in item for item in failures)
        )

    def test_retired_scan_rejects_malformed_retired_handlers(self) -> None:
        for label in ("missing-type", "wrong-type", "non-string-command"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                codex_home = Path(temporary).resolve() / "codex-home"
                codex_home.mkdir()
                target = codex_home / "hooks" / "subagent_scope.py"
                command = VALIDATOR.expected_hook_command(target, windows=VALIDATOR.os.name == "nt")
                if label == "missing-type":
                    handler: dict[str, object] = {"command": command}
                elif label == "wrong-type":
                    handler = {"type": "shell", "command": command}
                else:
                    handler = {"type": "command", "command": 123}
                (codex_home / "hooks.json").write_text(
                    json.dumps({"hooks": {"SubagentStart": [{"hooks": [handler]}]}}),
                    encoding="utf-8",
                )

                failures = VALIDATOR.retired_hook_failures(codex_home)

            self.assertTrue(failures)

    def test_retired_scan_rejects_python_code_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            retired = root / "old" / "subagent_scope.py"
            retired.parent.mkdir()
            retired.write_bytes(b"known retired scope fixture\n")
            code = f"exec(open({str(retired)!r}).read())"
            arguments = [sys.executable, "-c", code]
            windows = VALIDATOR.os.name == "nt"
            command = subprocess.list2cmdline(arguments) if windows else shlex.join(arguments)
            handler: dict[str, object] = {"type": "command", "command": command}
            if windows:
                handler["commandWindows"] = command
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": [handler]}]}}),
                encoding="utf-8",
            )
            known_digest = next(iter(VALIDATOR.RETIRED_HOOK_SHA256["subagent_scope.py"]))

            with mock.patch.object(VALIDATOR, "file_sha256", return_value=known_digest):
                failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("retired project Hook code" in item for item in failures))

    def test_hook_validation_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary).resolve() / "codex-home"
            codex_home.mkdir()
            (codex_home / "hooks.json").write_text('{"hooks": {}, "hooks": {}}', encoding="utf-8")

            failures = VALIDATOR.retired_hook_failures(codex_home)

        self.assertTrue(any("duplicate JSON key" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
