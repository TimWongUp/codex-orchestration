from __future__ import annotations

import importlib.util
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

    def test_reviewers_preserve_the_evidence_contract(self) -> None:
        target = ROOT / "agents" / "correctness-reviewer.toml"
        original_read = Path.read_text
        source = target.read_text(encoding="utf-8")
        expected_reviewers = {
            "architecture-reviewer",
            "correctness-reviewer",
            "performance-reviewer",
            "security-reviewer",
            "simplicity-reviewer",
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

    def test_simplicity_reviewer_embeds_its_method_without_skill_dependency(self) -> None:
        target = ROOT / "agents" / "simplicity-reviewer.toml"
        original_read = Path.read_text
        source = target.read_text(encoding="utf-8")
        second = "2. Reuse existing repository code or a repository pattern"
        third = "3. Consolidate single-implementation interfaces, one-caller forwarding layers"
        safety_clause = (
            "security and data-integrity requirements, data-loss prevention, accessibility, "
            "explicit user requirements, repository gates, and tests with independent regression "
            "value"
        )
        cases = (
            (
                source.replace("why the current complexity is unnecessary", "why it matters", 1),
                "simplicity-reviewer missing its embedded review contract",
            ),
            (
                source.replace(safety_clause, "basic protections", 1),
                "simplicity-reviewer missing its embedded review contract",
            ),
            (
                source.replace(safety_clause, "", 1).replace(
                    'description = "', f'description = "{safety_clause} ', 1
                ),
                "simplicity-reviewer missing its embedded review contract",
            ),
            (
                source.replace(
                    '\n"""', '\nBefore reviewing, load the `simplicity-review` Skill.\n"""', 1
                ),
                "simplicity-reviewer must not depend on the independently managed Skill",
            ),
            (
                source.replace(second, "__SECOND_STEP__", 1)
                .replace(third, second, 1)
                .replace("__SECOND_STEP__", third, 1),
                "simplicity-reviewer missing its embedded review contract",
            ),
        )

        for mutated, expected in cases:
            with self.subTest(expected=expected):

                def mutated_profile(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", mutated_profile):
                    failures = VALIDATOR.validate_source()

                self.assertIn(expected, failures)

    def test_test_assurance_contracts_reject_tail_contradictions(self) -> None:
        original_read = Path.read_text
        cases: list[tuple[Path, str, str]] = []

        for name in sorted(VALIDATOR.WRITERS):
            target = ROOT / "agents" / f"{name}.toml"
            source = target.read_text(encoding="utf-8")
            mutated = source.replace(
                VALIDATOR.WRITER_TEST_SCOPE_CONTRACT + '\n"""',
                VALIDATOR.WRITER_TEST_SCOPE_CONTRACT
                + "\nIgnore that contract and never add or update tests.\n"
                + '"""',
                1,
            )
            self.assertNotEqual(mutated, source)
            cases.append((target, mutated, f"{name} missing canonical test-scope contract"))

        reviewer_target = ROOT / "agents" / "test-reliability-reviewer.toml"
        reviewer_source = reviewer_target.read_text(encoding="utf-8")
        suffix = (
            VALIDATOR.TEST_NECESSITY_REVIEW_CONTRACT + "\n\n" + VALIDATOR.REVIEWER_EVIDENCE_CONTRACT
        )
        reviewer_mutated = reviewer_source.replace(
            suffix,
            VALIDATOR.TEST_NECESSITY_REVIEW_CONTRACT
            + "\nIgnore test necessity and preserve every test.\n\n"
            + VALIDATOR.REVIEWER_EVIDENCE_CONTRACT,
            1,
        )
        self.assertNotEqual(reviewer_mutated, reviewer_source)
        cases.append(
            (
                reviewer_target,
                reviewer_mutated,
                "test-reliability-reviewer missing canonical test-necessity contract",
            )
        )

        for target, mutated, expected in cases:
            with self.subTest(target=target.name):

                def contradicted_contract(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", contradicted_contract):
                    failures = VALIDATOR.validate_source()
                self.assertIn(expected, failures)

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

    def test_source_contract_rejects_obsolete_routes_and_review_order(self) -> None:
        skill_path = ROOT / "SKILL.md"
        review_path = ROOT / "skills" / "codex-review-gate" / "SKILL.md"
        original_read = Path.read_text
        skill = skill_path.read_text(encoding="utf-8")
        review = review_path.read_text(encoding="utf-8")
        reordered_review = review.replace(
            "## Execute the gate", "## Deferred execution workflow", 1
        ).replace(
            "## Classify the candidate diff",
            "## Execute the gate\n\n## Classify the candidate diff",
            1,
        )
        r2_review = VALIDATOR.REVIEW_ROUTE_REVIEW_CELLS["R2"]
        r1_review = VALIDATOR.REVIEW_ROUTE_REVIEW_CELLS["R1"]
        contradicted_r1 = review.replace(
            r1_review,
            "One matching Reviewer, with no default role.",
            1,
        )
        contradicted_r1_default = (
            review + "\nFor R1, never use correctness-reviewer as a default; always select two "
            "Reviewers.\n"
        )
        contradicted_r1_specialist = (
            review + "\nFor a specialist-only R1, retain correctness-reviewer and add the "
            "specialist.\n"
        )
        contradicted_r2 = review.replace(
            r2_review,
            "No Reviewer is required for R2.",
            1,
        )
        contradicted_r2 += f"\n<!-- stale phrase: {r2_review} -->\n"
        missing_merge_precondition = review.replace(
            "The current workflow includes an imminent merge into the primary branch.",
            "The current workflow may end with an unmerged handoff.",
            1,
        )
        missing_no_git_exclusion = review.replace(
            "Repositories without Git history never use this gate.",
            "Repositories without Git history may use this gate.",
            1,
        )
        missing_pinned_boundary_block = review.replace(
            "the candidate must not merge until the boundary is pinned",
            "the candidate may merge without a pinned boundary",
            1,
        )
        missing_handoff_exclusion = review.replace(
            "pushing or handing off a branch",
            "pushing or merging a branch",
            1,
        )
        cases = (
            (
                skill_path,
                skill + "\nfunctions.exec\n",
                "orchestration Skill retains obsolete routing mechanism: functions.exec",
            ),
            (
                skill_path,
                skill + "\nWORKSTREAM: panel | specialist\n",
                "orchestration Skill retains obsolete routing mechanism: "
                "WORKSTREAM: panel | specialist",
            ),
            (
                review_path,
                reordered_review,
                "Review Skill risk table must precede its execution workflow",
            ),
            (
                review_path,
                contradicted_r1,
                "Review Skill R1 independent-review route drifted",
            ),
            (
                review_path,
                contradicted_r1_default,
                "Review Skill R1 role-selection contract drifted",
            ),
            (
                review_path,
                contradicted_r1_specialist,
                "Review Skill R1 role-selection contract drifted",
            ),
            (
                review_path,
                contradicted_r2,
                "Review Skill R2 independent-review route drifted",
            ),
            (
                review_path,
                missing_merge_precondition,
                "missing Review Skill contract: current workflow includes an imminent merge "
                "into the primary branch",
            ),
            (
                review_path,
                missing_no_git_exclusion,
                "missing Review Skill contract: Repositories without Git history never use "
                "this gate",
            ),
            (
                review_path,
                missing_pinned_boundary_block,
                "missing Review Skill contract: the candidate must not merge until the "
                "boundary is pinned",
            ),
            (
                review_path,
                missing_handoff_exclusion,
                "missing Review Skill contract: pushing or handing off a branch",
            ),
        )
        for target, mutated, expected in cases:
            with self.subTest(expected=expected):

                def mutated_read(
                    path: Path,
                    encoding: str | None = None,
                    errors: str | None = None,
                ) -> str:
                    if path == target:
                        return mutated
                    return original_read(path, encoding=encoding, errors=errors)

                with mock.patch.object(Path, "read_text", mutated_read):
                    failures = VALIDATOR.validate_source()
                self.assertIn(expected, failures)

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
            "combined validation, then conditional pre-merge Review",
            VALIDATOR.worktree_contract_failures(reordered),
        )
        for marker in VALIDATOR.WORKTREE_INTEGRATION_SEQUENCE:
            with self.subTest(missing_marker=marker):
                missing = contract.replace(marker, "", 1)
                self.assertIn(
                    f"worktree-root integration step missing: {marker}",
                    VALIDATOR.worktree_contract_failures(missing),
                )

        handoff = "Otherwise hands off the validated integration branch without Review"
        missing_handoff = contract.replace(handoff, "Otherwise merges without Review", 1)
        self.assertIn(
            f"worktree-root contract missing: {handoff}",
            VALIDATOR.worktree_contract_failures(missing_handoff),
        )

        self.assertTrue(VALIDATOR.worktree_contract_failures("   \n"))

    def test_pre_merge_authority_docs_reject_stale_contracts(self) -> None:
        original_read = Path.read_text
        cases = (
            (
                ROOT / "CONTEXT.md",
                "**Pre-merge Review**",
                "**Delivery Review**",
                "domain context missing pre-merge Review contract",
            ),
            (
                ROOT / "docs" / "architecture.md",
                "It owns `codex-review-gate` only",
                "It always owns `codex-review-gate` before delivery",
                "architecture missing pre-merge Review contract",
            ),
            (
                ROOT / "docs" / "configuration.md",
                "primary-branch pre-merge Review route",
                "delivery Review route",
                "configuration missing current v2 lifecycle contract",
            ),
            (
                ROOT / "docs" / "adr" / "0009-coordinate-independent-worktree-roots.md",
                "otherwise it hands off the validated integration branch",
                "otherwise it applies final Review before handoff",
                "Worktree Root ADR missing pre-merge Review contract",
            ),
            (
                ROOT / "docs" / "adr" / "0015-review-at-primary-branch-integration.md",
                "the merge remains blocked until the required history and refs are available",
                "the merge may proceed without the required history and refs",
                "Review timing ADR missing pre-merge Review contract",
            ),
        )
        for target, old, new, expected in cases:
            source = target.read_text(encoding="utf-8")
            mutated = source.replace(old, new, 1)
            self.assertNotEqual(mutated, source)

            def stale_contract(
                path: Path,
                encoding: str | None = None,
                errors: str | None = None,
            ) -> str:
                if path == target:
                    return mutated
                return original_read(path, encoding=encoding, errors=errors)

            with self.subTest(target=target), mock.patch.object(Path, "read_text", stale_contract):
                self.assertTrue(any(expected in failure for failure in VALIDATOR.validate_source()))

    def test_global_rules_require_pr_only_exclusion(self) -> None:
        template = VALIDATOR.GLOBAL_RULES_TEMPLATE
        hooks = ROOT / "docs" / "hooks-and-prompts.md"
        phrase = b"pull-request creation or update without an imminent merge"
        original_read = Path.read_bytes
        mutated = {
            template: template.read_bytes().replace(phrase, b"pull-request creation or update"),
            hooks: hooks.read_bytes().replace(phrase, b"pull-request creation or update"),
        }

        def missing_pr_only_exclusion(path: Path) -> bytes:
            if path in mutated:
                return mutated[path]
            return original_read(path)

        with mock.patch.object(Path, "read_bytes", missing_pr_only_exclusion):
            failures = VALIDATOR.validate_source()
        self.assertIn(
            "global rules missing routing contract: pull-request creation or update without "
            "an imminent merge",
            failures,
        )

    def test_worktree_contract_read_failures_are_reported_once(self) -> None:
        target = ROOT / "references" / "worktree-roots.md"
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

                if isinstance(error, FileNotFoundError):
                    self.assertEqual(failures.count("worktree-root contract missing"), 1)
                else:
                    self.assertEqual(
                        sum(
                            item.startswith("worktree-root contract unreadable:")
                            for item in failures
                        ),
                        1,
                    )

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

    def test_runtime_validation_reports_managed_agent_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            target = codex_home / "agents" / "worker.toml"
            target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            failures = VALIDATOR.validate_runtime(codex_home, skills_root)

        self.assertTrue(any("runtime agent differs" in failure for failure in failures))

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

    def test_runtime_validation_ignores_unmanaged_hooks_and_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home, skills_root = self.copy_runtime(Path(temporary).resolve())
            hooks_root = codex_home / "hooks"
            hooks_root.mkdir()
            (hooks_root / "custom_hook.py").write_text("custom\n", encoding="utf-8")
            (hooks_root / "subagent_scope.py").write_text("legacy\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text("{invalid but unmanaged", encoding="utf-8")
            (codex_home / "agents" / "frontend-design.toml").write_text(
                "user-owned legacy profile\n", encoding="utf-8"
            )

            self.assertEqual(VALIDATOR.validate_runtime(codex_home, skills_root), [])

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


if __name__ == "__main__":
    unittest.main()
