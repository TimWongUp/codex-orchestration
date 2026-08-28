#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REVISION = "8b78b531ab965735c5dc74f6f7a219e1e37326df"
BUNDLED_SKILLS = {
    "codex-orchestration": ROOT,
    "codex-review-gate": ROOT / "skills" / "codex-review-gate",
    "diagnosing-bugs": ROOT / "skills" / "diagnosing-bugs",
    "prototype": ROOT / "skills" / "prototype",
}
THIRD_PARTY_SKILLS = {"diagnosing-bugs", "prototype"}
WRITERS = {"worker", "diagnosing-bugs-worker", "prototype-worker"}
REVIEWERS = {
    "architecture-reviewer",
    "correctness-reviewer",
    "performance-reviewer",
    "security-reviewer",
    "specialist-reviewer",
    "test-reliability-reviewer",
}
READERS = REVIEWERS | {
    "default",
    "explorer",
    "reference-researcher",
    "web-researcher",
    "adversarial-verifier",
    "expert",
}
REVIEWER_EVIDENCE_CONTRACT = (
    "Anchor findings to the assigned change boundary and risk. When a finding depends on a task "
    "or spec requirement or a repository standard, cite the applicable source and identify that "
    "evidence class; this is evidence discipline, not a generic Standards/Spec pass. Label "
    "heuristic concerns as judgment calls, report them only when they imply material risk within "
    "the assignment, and omit checks conclusively covered by current passing tooling unless that "
    "coverage is itself in question."
)
WRITER_TEST_SCOPE_CONTRACT = (
    "Keep test changes proportional to the assigned change's material risks. Add or update a test "
    "only when it supplies unique confidence at a correct observable seam and would fail for a "
    "credible regression; prefer extending an existing test at the lowest-cost appropriate layer. "
    "Use behavior rather than implementation order, private internals, mutable prose, or copies of "
    "production logic as the assertion boundary; count static analysis, schema validation, and "
    "stronger existing tests as protection when they already prove the property. Consolidate or "
    "remove a test within the assigned scope only when it adds no unique behavior or failure "
    "protection and equivalent protection remains; keep compatibility coverage only for current "
    "contracts, and never optimize for test count or a coverage percentage."
)
TEST_NECESSITY_REVIEW_CONTRACT = (
    "Assess whether each added or retained test earns its maintenance cost by protecting a current "
    "material behavior, credible failure path, boundary or contract, or regression. Prefer the "
    "lowest-cost correct seam and test layer that supply missing confidence, and recognize "
    "stronger existing tests or static tooling when they already prove the property. Treat "
    "coverage-chasing, "
    "production-logic copies, incidental implementation or prose checks, retired compatibility, "
    "and flaky or expensive setup without unique risk protection as removal or consolidation "
    "candidates. Recommend removal only when equivalent behavior and failure protection remain; "
    "never optimize for test count."
)
REVIEW_ROUTE_REVIEW_CELLS = {
    "R0": "None; the main agent inspects the complete diff and validates it.",
    "R1": "One Reviewer; select its role by the R1 rule below.",
    "R2": (
        "At least one matching Reviewer; add seats only for additional material hypotheses that "
        "need independent judgment, never to fill a quota."
    ),
    "R3": (
        "At least one focused Reviewer, main-agent remediation, then an `adversarial-verifier`."
    ),
}
R1_REVIEWER_SELECTION_CONTRACT = (
    "For R1, `correctness-reviewer` is the general default. When the sole material hypothesis is\n"
    "specifically architectural, security-related, performance-related, test-related, or "
    "otherwise\n"
    "specialist, select the matching Reviewer instead. The specialist replaces the default; it "
    "does not\n"
    "create a second seat for the same hypothesis."
)
FORBIDDEN_KEYS = {"model", "model_reasoning_effort", "service_tier"}
TASK_PACKAGE_LANGUAGES = {"en", "zh-CN"}
REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
WORKTREE_CONTRACT_PHRASES = (
    "independent Codex task and session",
    "user explicitly requested official Codex worktrees",
    "at most three nonterminal Worktree Roots",
    "at most eight spawned-agent threads",
    "host-enforced limit of eight or fewer",
    "same `explorer`, reviewer, worker, and specialist roles",
    "batch roles, not different agent types",
    "distinct official worktree",
    "`pending`, `running`, `handoff_ready`, `accepted`, `failed`, or `canceled`",
    "The Integration Root alone moves a handoff",
    "cannot confirm the host cap",
    "fails closed and does not spawn",
    "This keeps the batch at no more than three concurrent repository writers",
    "neither its main agent nor any local worker writes the repository",
    "moves every unlaunched `pending` reservation and every `handoff_ready` lane",
    "user's explicit rescoping",
    "prototype lane",
    "complete batch",
    "dedicated integration branch",
    "complete its R0-R3 review against the latest combined candidate diff",
    "Otherwise hands off the validated integration branch without Review",
    "Lane or intermediate review never substitutes for a required pre-merge Review",
    "Stop convergence",
    "A stopped batch is not",
)
WORKTREE_INTEGRATION_SEQUENCE = (
    "The Integration Root waits for the complete batch",
    "Serially merges accepted branches into a dedicated integration branch",
    "Runs the combined validation after all accepted branches are present",
    "If the current batch is about to merge the integration branch into the primary branch",
    "load `codex-review-gate` and complete its R0-R3 review",
)
FORBIDDEN_PUBLIC_PATTERNS = {
    "/" + "Users/": "absolute macOS user path",
    "C:" + "\\Users\\": "absolute Windows user path",
    "Asia" + "/Shanghai": "personal timezone",
    "xai/" + "grok": "machine-specific model route",
    "gpt-" + "5.6": "machine-specific model route",
    "deepseek-" + "v4": "machine-specific model route",
}
GLOBAL_RULES_START = b"<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->"
GLOBAL_RULES_END = b"<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->"
GLOBAL_RULES_TEMPLATE = ROOT / "examples" / "global-agents-block.md"
PROJECT_HOOK_FILENAMES = (
    "subagent_guard.py",
    "subagent_scope.py",
    "orchestration_route.py",
)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def model_routing_failures(source: str, *, allow_placeholders: bool) -> list[str]:
    """Validate the deliberately small TOML subset used by local model routing."""
    failures: list[str] = []
    top_level: dict[str, object] = {}
    overrides: list[dict[str, object]] = []
    panel_routes: dict[str, list[dict[str, object]]] = {}
    routes: dict[str, list[dict[str, object]]] = {}
    current = top_level

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section = re.fullmatch(
            r"\[\[(task_overrides|roles\.([A-Za-z0-9_-]+)|panel_routes\.([A-Za-z0-9_-]+))\]\]",
            line,
        )
        if section:
            if section.group(1) == "task_overrides":
                current = {}
                overrides.append(current)
            elif section.group(3):
                family = section.group(3)
                current = {}
                panel_routes.setdefault(family, []).append(current)
            else:
                role = section.group(2)
                current = {}
                assert role is not None
                routes.setdefault(role, []).append(current)
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if not assignment:
            failures.append(f"model routing line {line_number} is not supported TOML")
            continue
        key, raw_value = assignment.groups()
        if key in current:
            failures.append(f"model routing line {line_number} repeats {key}")
            continue
        try:
            current[key] = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError):
            failures.append(f"model routing line {line_number} has an invalid value")

    schema_version = top_level.get("schema_version")
    require(
        top_level.keys() == {"schema_version"},
        "model routing top-level fields are invalid",
        failures,
    )
    require(
        type(schema_version) is int and schema_version == 2,
        "model routing schema_version is invalid",
        failures,
    )
    allowed_roles = WRITERS | READERS
    if allow_placeholders:
        allowed_roles.add("ROLE_NAME")
    route_keys = {"model", "reasoning_effort", "service_tier"}
    override_keys = {"task_kind", "roles"} | route_keys
    panel_keys = {"phase"} | route_keys
    optional_keys = {"note"}

    if allow_placeholders:
        require(bool(overrides), "model routing template has no task override", failures)
    for index, entry in enumerate(overrides, 1):
        require(
            override_keys <= entry.keys(),
            f"routing override {index} is missing required fields",
            failures,
        )
        require(
            entry.keys() <= override_keys | optional_keys,
            f"routing override {index} has unknown fields",
            failures,
        )
        roles = entry.get("roles")
        require(
            isinstance(roles, list)
            and bool(roles)
            and all(isinstance(role, str) and role in allowed_roles for role in roles),
            f"routing override {index} has invalid roles",
            failures,
        )
        task_kind = entry.get("task_kind")
        require(
            isinstance(task_kind, str)
            and bool(task_kind.strip())
            and (allow_placeholders or task_kind != "TASK_KIND"),
            f"routing override {index} has invalid task_kind",
            failures,
        )

    require(
        set(panel_routes) == {"gpt", "third_party"},
        "model routing panel families are invalid",
        failures,
    )
    panel_entries: list[dict[str, object]] = []
    for family, entries in panel_routes.items():
        primary_models: set[str] = set()
        family_models: set[str] = set()
        for index, entry in enumerate(entries, 1):
            require(
                panel_keys <= entry.keys(),
                f"routing panel {family}[{index}] is missing required fields",
                failures,
            )
            require(
                entry.keys() <= panel_keys | optional_keys,
                f"routing panel {family}[{index}] has unknown fields",
                failures,
            )
            phase = entry.get("phase")
            require(
                isinstance(phase, str) and phase in {"primary", "fallback"},
                f"routing panel {family}[{index}] has invalid phase",
                failures,
            )
            model = entry.get("model")
            if isinstance(model, str):
                require(
                    model not in family_models,
                    f"routing panel {family} repeats model: {model}",
                    failures,
                )
                family_models.add(model)
                if phase == "primary":
                    primary_models.add(model)
            panel_entries.append(entry)
        require(
            len(primary_models) >= 2,
            f"routing panel {family} needs at least two distinct primary models",
            failures,
        )

    require(bool(routes), "model routing has no role routes", failures)
    for role, entries in routes.items():
        require(role in allowed_roles, f"model routing has unknown role: {role}", failures)
        for index, entry in enumerate(entries, 1):
            require(
                route_keys <= entry.keys(),
                f"routing route {role}[{index}] is missing required fields",
                failures,
            )
            require(
                entry.keys() <= route_keys | optional_keys,
                f"routing route {role}[{index}] has unknown fields",
                failures,
            )

    all_entries = (
        overrides + panel_entries + [item for entries in routes.values() for item in entries]
    )
    for entry in all_entries:
        model = entry.get("model")
        if not isinstance(model, str):
            model_is_valid = False
        elif allow_placeholders:
            model_is_valid = bool(model.strip()) and model.startswith("MODEL_ID_")
        else:
            model_is_valid = bool(model.strip()) and not model.startswith("MODEL_ID_")
        require(
            model_is_valid,
            "model routing has an invalid model",
            failures,
        )
        reasoning_effort = entry.get("reasoning_effort")
        valid_reasoning = isinstance(reasoning_effort, str) and (
            reasoning_effort in REASONING_EFFORTS
            or (allow_placeholders and reasoning_effort == "REASONING_LEVEL")
        )
        require(
            valid_reasoning,
            "model routing has an invalid reasoning_effort",
            failures,
        )
        service_tier = entry.get("service_tier")
        valid_service_tier = isinstance(service_tier, str) and (
            service_tier in {"priority", "standard"}
            or (allow_placeholders and service_tier == "SERVICE_TIER")
        )
        require(
            valid_service_tier,
            "model routing has an invalid service_tier",
            failures,
        )
        note = entry.get("note")
        require(
            note is None or (isinstance(note, str) and bool(note.strip())),
            "model routing has an invalid note",
            failures,
        )
    return failures


def routing_example_failures(source: str) -> list[str]:
    """Validate the placeholder routing template shipped by the repository."""
    return model_routing_failures(source, allow_placeholders=True)


def preferences_failures(source: str, *, allow_placeholder: bool = False) -> list[str]:
    """Validate the canonical TOML subset used by local task-package preferences."""
    failures: list[str] = []
    values: dict[str, object] = {}

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if not assignment:
            failures.append(f"preferences line {line_number} is not supported TOML")
            continue
        key, raw_value = assignment.groups()
        if key in values:
            failures.append(f"preferences line {line_number} repeats {key}")
            continue
        if raw_value == "1":
            values[key] = 1
            continue
        string_value = re.fullmatch(r'(["\'])([A-Za-z-]+)\1', raw_value)
        if string_value:
            values[key] = string_value.group(2)
        else:
            failures.append(f"preferences line {line_number} has an invalid value")

    require(
        values.keys() == {"schema_version", "task_package_language"},
        "preferences fields are invalid",
        failures,
    )
    schema_version = values.get("schema_version")
    require(
        type(schema_version) is int and schema_version == 1,
        "preferences schema_version is invalid",
        failures,
    )
    languages = set(TASK_PACKAGE_LANGUAGES)
    if allow_placeholder:
        languages.add("LANGUAGE")
    language = values.get("task_package_language")
    require(
        isinstance(language, str) and language in languages,
        "preferences task_package_language is invalid",
        failures,
    )
    return failures


def top_level_values(source: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in source.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+)\s*=\s*(['\"])(.*?)\2\s*$", line)
        if match:
            values[match.group(1)] = match.group(3)
    return values


def top_level_multiline_value(source: str, key: str) -> str | None:
    in_multiline_string = False
    top_level_end = len(source)
    offset = 0
    for line in source.splitlines(keepends=True):
        if not in_multiline_string and re.fullmatch(
            r"\s*\[\[?.+?\]\]?\s*(?:#.*)?", line.rstrip("\r\n")
        ):
            top_level_end = offset
            break
        if line.count('"""') % 2:
            in_multiline_string = not in_multiline_string
        offset += len(line)

    top_level = source[:top_level_end]
    pattern = re.compile(
        rf'^\s*{re.escape(key)}\s*=\s*"""(.*?)^\s*"""\s*$',
        re.MULTILINE | re.DOTALL,
    )
    matches = pattern.findall(top_level)
    return matches[0] if len(matches) == 1 else None


def markdown_frontmatter_values(source: str) -> dict[str, str]:
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*?)\s*", line.strip())
        if match:
            values[match.group(1)] = match.group(2).strip("'\"")
    return {}


def source_version_failures(project: str, skill: str) -> list[str]:
    failures: list[str] = []
    project_version = top_level_values(project).get("version")
    skill_version = markdown_frontmatter_values(skill).get("version")
    frontmatter_end = skill.find("\n---", 3) if skill.startswith("---\n") else -1
    frontmatter = skill[4:frontmatter_end] if frontmatter_end >= 0 else ""
    version_fields = re.findall(r"^\s*version:\s*.+$", frontmatter, re.MULTILINE)
    project_version_fields = re.findall(r"^version\s*=\s*.+$", project, re.MULTILINE)
    require(
        len(project_version_fields) == 1,
        "project version must appear exactly once",
        failures,
    )
    require(
        len(version_fields) == 1,
        "Skill front matter version must appear exactly once",
        failures,
    )
    require(
        skill_version == project_version,
        "Skill front matter version must match project version",
        failures,
    )
    return failures


def read_required_text(path: Path, label: str, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        failures.append(f"{label} missing")
    except (OSError, UnicodeError) as error:
        failures.append(f"{label} unreadable: {error}")
    return ""


def worktree_contract_failures(source: str) -> list[str]:
    failures: list[str] = []
    normalized = re.sub(r"\s+", " ", source)
    for phrase in WORKTREE_CONTRACT_PHRASES:
        require(phrase in normalized, f"worktree-root contract missing: {phrase}", failures)

    barrier_match = re.search(
        r"^## Integration barrier\s*$([\s\S]*?)(?=^## |\Z)", source, re.MULTILINE
    )
    require(barrier_match is not None, "worktree-root integration barrier missing", failures)
    barrier = re.sub(r"\s+", " ", barrier_match.group(1)) if barrier_match is not None else ""
    positions = [barrier.find(marker) for marker in WORKTREE_INTEGRATION_SEQUENCE]
    for marker, position in zip(WORKTREE_INTEGRATION_SEQUENCE, positions):
        require(
            position >= 0,
            f"worktree-root integration step missing: {marker}",
            failures,
        )
    if all(position >= 0 for position in positions):
        require(
            positions == sorted(set(positions)),
            "worktree-root integration sequence must be complete batch, serial merge, "
            "combined validation, then conditional pre-merge Review",
            failures,
        )
    return failures


def path_is_link_like(path: Path) -> bool:
    """Reject symlinks and Windows reparse points such as NTFS junctions."""
    if path.is_symlink():
        return True
    if os.name != "nt" or not os.path.lexists(path):
        return False
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & 0x400)


def canonical_selected_root(path: Path) -> Path:
    """Resolve parent aliases while leaving the selected leaf available for link checks."""
    absolute = path.expanduser().absolute()
    return absolute.parent.resolve(strict=False) / absolute.name


def allowed_platform_path_alias(path: Path) -> bool:
    return sys.platform == "darwin" and path in {
        Path("/etc"),
        Path("/tmp"),
        Path("/var"),
    }


def skill_document_name(source: str) -> str | None:
    lines = source.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        boundary = lines.index("---", 1)
    except ValueError:
        return None
    for line in lines[1:boundary]:
        match = re.match(r"^name:\s*(.+?)\s*$", line)
        if not match:
            continue
        value = match.group(1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else None
    return None


def has_symlink_component(path: Path, boundary: Path) -> bool:
    current = path
    while current != boundary:
        if path_is_link_like(current):
            return True
        if current == current.parent:
            return False
        current = current.parent
    return path_is_link_like(boundary)


def first_symlink_component(path: Path) -> Path | None:
    if ".." in path.parts:
        return path
    current = path.absolute()
    while True:
        if path_is_link_like(current) and not allowed_platform_path_alias(current):
            return current
        if current == current.parent:
            return None
        current = current.parent


def files_equal(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def managed_global_rules_ranges(content: bytes) -> tuple[str, list[tuple[int, int]]]:
    """Parse exact standalone managed-block markers without normalizing user bytes."""
    ranges: list[tuple[int, int]] = []
    offset = 0
    open_start: int | None = None
    diagnostics = False
    saw_marker = False

    for raw_line in content.splitlines(keepends=True):
        if raw_line.endswith(b"\r\n"):
            line = raw_line[:-2]
        elif raw_line.endswith(b"\n"):
            line = raw_line[:-1]
        else:
            line = raw_line
        line_end = offset + len(raw_line)
        if line == GLOBAL_RULES_START:
            saw_marker = True
            if open_start is not None:
                diagnostics = True
            else:
                open_start = offset
        elif line == GLOBAL_RULES_END:
            saw_marker = True
            if open_start is None:
                diagnostics = True
            else:
                ranges.append((open_start, line_end))
                open_start = None
        elif GLOBAL_RULES_START in line or GLOBAL_RULES_END in line:
            diagnostics = True
        offset = line_end

    if open_start is not None:
        diagnostics = True
    if not saw_marker and (GLOBAL_RULES_START in content or GLOBAL_RULES_END in content):
        diagnostics = True
    if diagnostics:
        return "corrupt", []
    return ("complete" if saw_marker else "none"), ranges


def active_global_rules_target(codex_home: Path) -> tuple[Path | None, str | None]:
    """Resolve the one global instruction file Codex loads without traversing links."""
    if path_is_link_like(codex_home):
        return None, f"Codex home linked or conflicting: {codex_home}"
    linked = first_symlink_component(codex_home)
    if linked is not None:
        return None, f"Codex home has linked or unsafe path component: {linked}"
    codex_home = canonical_selected_root(codex_home)
    override = codex_home / "AGENTS.override.md"
    base = codex_home / "AGENTS.md"
    if path_is_link_like(override) or (override.exists() and not override.is_file()):
        return None, f"global override linked or conflicting: {override}"
    if override.is_file():
        try:
            if override.read_bytes().strip():
                return override, None
        except OSError as error:
            return None, f"global override unreadable: {override}: {error}"
    if path_is_link_like(base) or (base.exists() and not base.is_file()):
        return None, f"global instructions linked or conflicting: {base}"
    return base, None


def validate_global_rules(codex_home: Path) -> list[str]:
    """Require one canonical managed block in the active global instruction file."""
    failures: list[str] = []
    codex_home = canonical_selected_root(codex_home)
    target, target_error = active_global_rules_target(codex_home)
    if target_error is not None or target is None:
        return [target_error or "global instructions target could not be resolved"]
    try:
        canonical = GLOBAL_RULES_TEMPLATE.read_bytes().replace(b"\r\n", b"\n")
    except OSError as error:
        return [f"global rules template unreadable: {GLOBAL_RULES_TEMPLATE}: {error}"]

    for candidate in (codex_home / "AGENTS.md", codex_home / "AGENTS.override.md"):
        if path_is_link_like(candidate) or (candidate.exists() and not candidate.is_file()):
            failures.append(f"global instructions linked or conflicting: {candidate}")
            continue
        if not candidate.is_file():
            if candidate == target:
                failures.append(f"global instructions missing: {candidate}")
            continue
        try:
            content = candidate.read_bytes()
        except OSError as error:
            failures.append(f"global instructions unreadable: {candidate}: {error}")
            continue
        state, ranges = managed_global_rules_ranges(content)
        if state == "corrupt" or len(ranges) > 1:
            failures.append(f"global rules markers corrupt or duplicated: {candidate}")
            continue
        if candidate != target:
            if ranges:
                failures.append(f"inactive global instructions retain managed block: {candidate}")
            continue
        if len(ranges) != 1:
            failures.append(f"global rules block missing: {candidate}")
            continue
        start, end = ranges[0]
        installed = content[start:end].replace(b"\r\n", b"\n")
        require(
            installed == canonical,
            f"global rules block differs: {candidate}",
            failures,
        )
    return failures


def public_text_files() -> list[Path]:
    suffixes = {".md", ".toml", ".py", ".yml", ".yaml", ".json"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix in suffixes
    ]


def pinned_model_keys(source: str) -> set[str]:
    return FORBIDDEN_KEYS.intersection(top_level_values(source))


def public_pattern_failures(label: str, source: str) -> list[str]:
    return [
        f"{description} in {label}"
        for pattern, description in FORBIDDEN_PUBLIC_PATTERNS.items()
        if pattern in source
    ]


def validate_source() -> list[str]:
    failures: list[str] = []
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    review_skill = read_required_text(
        ROOT / "skills" / "codex-review-gate" / "SKILL.md", "Review Skill", failures
    )
    install_contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    worker_contract = (ROOT / "references" / "worker-writing.md").read_text(encoding="utf-8")
    read_only_contract = read_required_text(
        ROOT / "references" / "read-only-collaboration.md",
        "read-only collaboration contract",
        failures,
    )
    lifecycle_contract = read_required_text(
        ROOT / "references" / "collaboration-lifecycle.md",
        "collaboration lifecycle contract",
        failures,
    )
    worktree_contract = read_required_text(
        ROOT / "references" / "worktree-roots.md", "worktree-root contract", failures
    )
    model_routing = (ROOT / "references" / "model-routing.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    context = read_required_text(ROOT / "CONTEXT.md", "domain context", failures)
    worktree_adr = read_required_text(
        ROOT / "docs" / "adr" / "0009-coordinate-independent-worktree-roots.md",
        "Worktree Root ADR",
        failures,
    )
    review_timing_adr = read_required_text(
        ROOT / "docs" / "adr" / "0015-review-at-primary-branch-integration.md",
        "Review timing ADR",
        failures,
    )
    normalized_skill = re.sub(r"\s+", " ", skill)
    normalized_review = re.sub(r"\s+", " ", review_skill)
    normalized_read_only = re.sub(r"\s+", " ", read_only_contract)
    normalized_lifecycle = re.sub(r"\s+", " ", lifecycle_contract)

    failures.extend(source_version_failures(project, skill))
    failures.extend(source_version_failures(project, review_skill))

    for phrase in (
        "task_package_language",
        "Single writer",
        "Do not create a worktree unless the user explicitly requests one",
        'fork_turns="none"',
        "collaboration-tool schemas are the sole authority",
        "dependency barrier",
        "Before selecting a model for any delegation",
        "unisolated prompt injection",
        "Derived agents do not load or execute this Skill",
        "call collaboration tools, or orchestrate any agent",
        "Independent Worktree Roots",
        "same local orchestration authority as any other",
        "separately authorizes only its selected R1-R3 read-only Reviewers",
        "without reapplying the ordinary delegation threshold",
    ):
        require(phrase in normalized_skill, f"missing Skill contract: {phrase}", failures)

    for phrase in (
        "Before creating two or more read-only agents, read "
        "[references/read-only-collaboration.md](references/read-only-collaboration.md)",
        "Before selecting a model for any delegation, read "
        "[references/model-routing.md](references/model-routing.md)",
        "Before creating a writable worker, read "
        "[references/worker-writing.md](references/worker-writing.md)",
        "read [references/worktree-roots.md](references/worktree-roots.md) before creating or "
        "coordinating official Worktree Roots",
        "or stopping agent work, read "
        "[references/collaboration-lifecycle.md](references/collaboration-lifecycle.md)",
    ):
        require(phrase in normalized_skill, f"missing Skill reference pointer: {phrase}", failures)

    require(
        re.search(r"^#{1,6}\s+Review gate\b.*$", skill, re.IGNORECASE | re.MULTILINE) is None,
        "orchestration Skill must not redefine the Review gate",
        failures,
    )
    for forbidden in ("functions.exec", "WORKSTREAM: panel | specialist"):
        require(
            forbidden not in skill,
            f"orchestration Skill retains obsolete routing mechanism: {forbidden}",
            failures,
        )

    for phrase in (
        "coverage",
        "panel",
        "hybrid",
        "semantic instructions, not required labels",
        "missing labels never make an",
        "same question",
        "Majority vote is not the decision rule",
        "does not load or execute `codex-orchestration`",
        "call collaboration tools, or orchestrate any other agent",
    ):
        require(
            phrase in normalized_read_only,
            f"read-only collaboration contract missing: {phrase}",
            failures,
        )

    for phrase in (
        "same-thread follow-up",
        "followup_task",
        "interrupt_agent",
        "earlier final notification",
        "fresh agent-tree snapshot",
        "ordinary final notification is sufficient",
        "Slow progress, sparse output",
        "no prior lease is extended",
        "explicitly stops subagent work",
    ):
        require(
            phrase in normalized_lifecycle,
            f"collaboration lifecycle contract missing: {phrase}",
            failures,
        )

    for phrase in (
        "primary-branch integration control, not a task-completion or ordinary-delegation control",
        "authorizes its selected R1-R3 read-only Reviewers",
        "Git repository with committed source and primary-branch histories",
        "current workflow includes an imminent merge into the primary branch",
        "pin the latest candidate diff from the target merge base to the candidate head",
        "the candidate must not merge until the boundary is pinned",
        "Repositories without Git history never use this gate",
        "Opening or updating a pull request",
        "pushing or handing off a branch",
        "Choose the highest matching level",
        "Changed line or file counts never determine a level",
        "R0 needs no Agent",
        "localized runtime, public-contract, managed-policy",
        "leaves no material failure hypothesis",
        "exactly one material failure hypothesis",
        "classify the change as R0 only when every R0 condition and exclusion is satisfied",
        "independent judgment could change",
        "self-contained illustrative or demonstration artifact",
        "the mere presence of runtime behavior is not",
        "broad or hard-to-recover public contract",
        "`correctness-reviewer` is the general default",
        "The specialist replaces the default; it does not create a second seat",
        "At least one matching Reviewer",
        "At least one focused Reviewer, main-agent remediation, then an `adversarial-verifier`",
        "send the original Reviewer a same-thread targeted follow-up",
        "it is not a new full Review",
        "without a separate current-turn request",
        "classify it as R2. This fail-closed fallback",
        "explicit user prohibition on subagents or Reviewers still wins",
        "about to merge a pull request, branch, or accepted Worktree integration branch",
        "Classify one final integrated candidate diff",
    ):
        require(phrase in normalized_review, f"missing Review Skill contract: {phrase}", failures)
    require(
        0 <= review_skill.find("| R3 |") < review_skill.find("## Execute the gate"),
        "Review Skill risk table must precede its execution workflow",
        failures,
    )
    for level, expected_review in REVIEW_ROUTE_REVIEW_CELLS.items():
        rows = [line for line in review_skill.splitlines() if line.startswith(f"| {level} |")]
        require(
            len(rows) == 1 and rows[0].endswith(f"| {expected_review} |"),
            f"Review Skill {level} independent-review route drifted",
            failures,
        )
    r1_role_rule_removed = review_skill.replace(R1_REVIEWER_SELECTION_CONTRACT, "", 1).lower()
    require(
        review_skill.count(R1_REVIEWER_SELECTION_CONTRACT) == 1
        and f"{R1_REVIEWER_SELECTION_CONTRACT}\n\n## Execute the gate" in review_skill
        and all(
            phrase not in r1_role_rule_removed
            for phrase in (
                "correctness-reviewer",
                "correctness reviewer",
                "correctness review",
                "default",
                "specialist",
            )
        ),
        "Review Skill R1 role-selection contract drifted",
        failures,
    )

    failures.extend(worktree_contract_failures(worktree_contract))

    for phrase in (
        "latest host-generated system or developer model binding",
        "explicit `model_switch`",
        "panel_routes.gpt",
        "panel_routes.third_party",
        "fails closed to `panel_routes.gpt`",
        "brief makes\nthe workstream clear",
        "Specialist workstreams use ordinary role routes",
        "host precondition",
        "at least two distinct usable models",
        "ordinary task overrides do not",
        "no distinct model remains",
    ):
        require(phrase in model_routing, f"missing model routing contract: {phrase}", failures)

    for name, path in BUNDLED_SKILLS.items():
        bundled = read_required_text(path / "SKILL.md", f"bundled Skill {name}", failures)
        require(
            skill_document_name(bundled) == name,
            f"bundled Skill name mismatch: {name}",
            failures,
        )
        if name in THIRD_PARTY_SKILLS:
            for phrase in (
                "author: Matt Pocock",
                "source: https://github.com/mattpocock/skills",
                f"source_revision: {UPSTREAM_REVISION}",
                "license: MIT",
            ):
                require(phrase in bundled, f"{name} missing attribution: {phrase}", failures)

    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    upstream_license = (ROOT / "licenses" / "mattpocock-skills-MIT.txt").read_text(encoding="utf-8")
    require(
        "Original author: Matt Pocock" in notices, "third-party author notice missing", failures
    )
    require(
        f"`{UPSTREAM_REVISION}`" in notices,
        "third-party source revision notice missing or stale",
        failures,
    )
    require(
        "Copyright (c) 2026 Matt Pocock" in upstream_license,
        "upstream MIT copyright notice missing",
        failures,
    )

    profiles: dict[str, dict[str, str]] = {}
    profile_sources: dict[str, str] = {}
    profile_instructions: dict[str, str] = {}
    for path in sorted((ROOT / "agents").glob("*.toml")):
        source = path.read_text(encoding="utf-8")
        values = top_level_values(source)
        name = values.get("name")
        require(name is not None, f"missing agent name: {path.name}", failures)
        if name:
            profiles[name] = values
            profile_sources[name] = source
            instructions = top_level_multiline_value(source, "developer_instructions")
            require(
                instructions is not None,
                f"missing or ambiguous developer_instructions: {path.name}",
                failures,
            )
            profile_instructions[name] = instructions or ""
            require(name == path.stem, f"agent filename/name mismatch: {path.name}", failures)
        pinned = pinned_model_keys(source)
        require(not pinned, f"agent pins model settings: {path.name}: {sorted(pinned)}", failures)
    require(set(profiles) == WRITERS | READERS, "agent role set does not match contract", failures)
    for name in WRITERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "workspace-write",
            f"{name} must be writable",
            failures,
        )
        require(
            "labels and fixed fields are not required" in profile_sources.get(name, ""),
            f"{name} does not accept natural-language briefs",
            failures,
        )
        require(
            "necessary adjacent files" in profile_sources.get(name, ""),
            f"{name} does not permit the smallest complete adjacent change",
            failures,
        )
        require(
            profile_instructions.get(name, "").rstrip().endswith(WRITER_TEST_SCOPE_CONTRACT),
            f"{name} missing canonical test-scope contract",
            failures,
        )
    for name in READERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "read-only",
            f"{name} must be read-only",
            failures,
        )
    for name in REVIEWERS:
        instructions = profile_instructions.get(name, "")
        require(
            instructions.rstrip().endswith(REVIEWER_EVIDENCE_CONTRACT),
            f"{name} missing canonical reviewer evidence contract",
            failures,
        )
    require(
        profile_instructions.get("test-reliability-reviewer", "")
        .rstrip()
        .endswith(TEST_NECESSITY_REVIEW_CONTRACT + "\n\n" + REVIEWER_EVIDENCE_CONTRACT),
        "test-reliability-reviewer missing canonical test-necessity contract",
        failures,
    )
    derived_identity = (
        "derived, non-orchestrating agent",
        "Do not load or execute the codex-orchestration Skill",
        "call collaboration tools",
        "create descendants",
        "panel or hybrid work",
    )
    for name, source in profile_sources.items():
        for phrase in derived_identity:
            require(
                phrase in source,
                f"{name} missing derived-agent identity contract: {phrase}",
                failures,
            )
    require(
        "load the `diagnosing-bugs` Skill"
        in (ROOT / "agents" / "diagnosing-bugs-worker.toml").read_text(encoding="utf-8"),
        "diagnosing-bugs-worker does not load its method Skill",
        failures,
    )
    require(
        "load the `prototype` Skill"
        in (ROOT / "agents" / "prototype-worker.toml").read_text(encoding="utf-8"),
        "prototype-worker does not load its method Skill",
        failures,
    )
    for phrase in ("returns a checkpoint instead of guessing", "at most three writable rounds"):
        require(
            phrase in worker_contract,
            f"worker contract missing lease boundary: {phrase}",
            failures,
        )
    require(
        "Community popularity is not proof of correctness"
        in (ROOT / "agents" / "web-researcher.toml").read_text(encoding="utf-8"),
        "web-researcher lost evidence hierarchy",
        failures,
    )

    for phrase in (
        "main Skill's natural-language brief contract",
        "intended change and handoff focus",
        "recover ordinary implementation context",
        "necessary adjacent files",
        "selected through [model-routing.md](model-routing.md)",
        "complete diff",
    ):
        require(
            phrase in worker_contract,
            f"worker contract missing flexible brief: {phrase}",
            failures,
        )

    require(
        (ROOT / "skills" / "diagnosing-bugs" / "scripts" / "hitl-loop.template.ps1").is_file(),
        "Windows HITL template missing",
        failures,
    )

    for phrase in (
        "Deterministic installation and uninstall contract",
        "`scripts/install.py` is the only mutation implementation",
        "dry run",
        "`--apply`",
        "`--uninstall`",
        "`--language en` or `--language zh-CN`",
        "CODEX-ORCHESTRATION:GLOBAL-RULES",
        "AGENTS.override.md",
        "byte-for-byte",
        "Do not register the repository root as one Skill",
        "one-time migration from links or a different checkout",
        "examples/preferences.toml",
        "--skills-root",
        "caught mutation or verification failure",
        "abrupt process termination",
        "does not confirm the resolved model",
        "changed managed file is a conflict",
        "ancestor of the source checkout",
        "filesystem identity",
        "same-directory staged file",
        "verified uninstall commit",
    ):
        require(phrase in install_contract, f"missing install contract: {phrase}", failures)

    for phrase in (
        "model-visible collaboration-tool schemas own call mechanics",
        'fork_turns="none"',
        "dependency barrier",
        "follow-up invalidates earlier completion evidence",
        "latest host-generated system or developer model binding",
        "Ordinary `single`, `coverage`, worker, and Hybrid specialist delegation do not",
        "Every task, panel, and role entry includes `service_tier",
        "validates any saved task-package language and model route",
        "does not confirm the resolved model",
        "primary-branch pre-merge Review route",
        "The merge-owning root executes",
        "inability to pin it blocks the merge",
    ):
        require(
            phrase in configuration,
            f"configuration missing current v2 lifecycle contract: {phrase}",
            failures,
        )
    for source, label, phrases in (
        (
            architecture,
            "architecture",
            (
                "It owns `codex-review-gate` only when it also owns the primary-branch merge",
                "integration-branch handoff",
                "the merge remains blocked until the required history and refs are available",
            ),
        ),
        (
            context,
            "domain context",
            (
                "**Pre-merge Review**",
                "latest pinned candidate diff immediately before",
                "It owns Pre-merge Review only when it also owns the primary-branch merge",
            ),
        ),
        (
            worktree_adr,
            "Worktree Root ADR",
            (
                "When the Integration Root also owns the primary-branch merge",
                "otherwise it hands off the validated integration branch",
            ),
        ),
        (
            review_timing_adr,
            "Review timing ADR",
            (
                "[ADR 0009](0009-coordinate-independent-worktree-roots.md)",
                "the merge remains blocked until the required history and refs are available",
            ),
        ),
    ):
        normalized_source = re.sub(r"\s+", " ", source)
        for phrase in phrases:
            require(
                phrase in normalized_source,
                f"{label} missing pre-merge Review contract: {phrase}",
                failures,
            )
    for pattern in (
        r"terminal[- ]markers?",
        r"hashed session and agent identifiers",
        r"codex-orchestration-subagents",
    ):
        require(
            re.search(pattern, configuration, re.IGNORECASE) is None,
            f"configuration retains obsolete terminal-marker contract: {pattern}",
            failures,
        )

    for path in public_text_files():
        relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        text = read_required_text(path, f"public source {relative}", failures)
        failures.extend(public_pattern_failures(relative, text))

    require(
        (ROOT / "docs" / "adr" / "0007-pure-v2-collaboration-lifecycle.md").is_file(),
        "pure v2 collaboration ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0008-deterministic-installer-and-global-rules.md").is_file(),
        "deterministic installer ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0010-retire-orchestration-hook-and-rigid-briefs.md").is_file(),
        "Hook and rigid-brief retirement ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0011-separate-delivery-review-from-orchestration.md").is_file(),
        "Review authority-boundary ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0012-remove-legacy-cleanup-from-installation.md").is_file(),
        "legacy cleanup boundary ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0013-safe-current-projection-uninstall.md").is_file(),
        "current projection uninstall ADR missing",
        failures,
    )
    require(
        (ROOT / "docs" / "adr" / "0015-review-at-primary-branch-integration.md").is_file(),
        "primary-branch Review timing ADR missing",
        failures,
    )
    for script in PROJECT_HOOK_FILENAMES:
        require(
            not os.path.lexists(ROOT / "hooks" / script),
            f"project Hook remains in source: {script}",
            failures,
        )

    installer = ROOT / "scripts" / "install.py"
    require(installer.is_file(), "deterministic installer missing", failures)
    if installer.is_file():
        try:
            compile(installer.read_text(encoding="utf-8"), str(installer), "exec")
        except SyntaxError as error:
            failures.append(f"installer syntax error: {error}")
    try:
        global_rules = GLOBAL_RULES_TEMPLATE.read_bytes()
    except OSError as error:
        failures.append(f"global rules template unreadable: {error}")
    else:
        state, ranges = managed_global_rules_ranges(global_rules)
        require(
            state == "complete" and len(ranges) == 1 and ranges[0] == (0, len(global_rules)),
            "global rules template must be one complete managed block",
            failures,
        )
        hooks_and_prompts = (ROOT / "docs" / "hooks-and-prompts.md").read_bytes()
        require(
            global_rules.rstrip() in hooks_and_prompts,
            "Hook documentation does not contain the canonical global rules block",
            failures,
        )
        decoded_global_rules = global_rules.decode("utf-8")
        for phrase in (
            "Root tasks load `codex-orchestration` before creating, coordinating, or waiting",
            "independent Worktree Roots",
            "simple tasks and ordinary documentation stay with the main agent",
            "Before merging a pull request, branch, or accepted Worktree integration branch",
            "Ordinary task completion, unmerged handoff",
            "pull-request creation or update without an imminent merge",
            "repositories without Git history do not trigger it",
            "R1-R3 route authorizes only the selected read-only Reviewers",
            "classifies the candidate rather than starting a Reviewer",
            "current explicit user prohibition still wins",
        ):
            require(
                phrase in decoded_global_rules,
                f"global rules missing routing contract: {phrase}",
                failures,
            )
    routing_example = (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8")
    failures.extend(routing_example_failures(routing_example))
    preferences_example = (ROOT / "examples" / "preferences.toml").read_text(encoding="utf-8")
    failures.extend(preferences_failures(preferences_example, allow_placeholder=True))
    routing_contract = (ROOT / "references" / "model-routing.md").read_text(encoding="utf-8")
    for phrase in (
        "effective route",
        "first candidate, not a hard pin",
        "panel_routes.gpt",
        "panel_routes.third_party",
        "worker-round-three",
        "host precondition",
    ):
        require(phrase in routing_contract, f"routing contract missing: {phrase}", failures)
    return failures


def validate_runtime(codex_home: Path, skills_root: Path) -> list[str]:
    failures: list[str] = []
    for label, root in (("Codex home", codex_home), ("Skill root", skills_root)):
        if path_is_link_like(root):
            failures.append(f"runtime {label} linked or conflicting: {root}")
            continue
        linked = first_symlink_component(root)
        if linked is not None:
            failures.append(f"runtime {label} has linked path component: {linked}")
    if failures:
        return failures
    codex_home = canonical_selected_root(codex_home)
    skills_root = canonical_selected_root(skills_root)

    for name, source_root in BUNDLED_SKILLS.items():
        target_root = skills_root / name
        if path_is_link_like(target_root) or not target_root.is_dir():
            failures.append(f"runtime Skill missing, linked, or conflicting: {target_root}")
            continue
        if name == "codex-orchestration":
            source_files = [source_root / "SKILL.md"]
            source_files.extend(
                path for path in (source_root / "references").rglob("*") if path.is_file()
            )
        else:
            source_files = [
                path
                for path in source_root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            ]
        for source in source_files:
            relative = source.relative_to(source_root)
            target = target_root / relative
            require(
                not has_symlink_component(target, target_root)
                and target.is_file()
                and files_equal(target, source),
                f"runtime Skill file differs: {target}",
                failures,
            )

    agents_root = codex_home / "agents"
    if path_is_link_like(agents_root) or not agents_root.is_dir():
        failures.append(f"runtime Agent directory missing, linked, or conflicting: {agents_root}")
    else:
        for source in sorted((ROOT / "agents").glob("*.toml")):
            target = agents_root / source.name
            require(
                not path_is_link_like(target) and target.is_file() and files_equal(target, source),
                f"runtime agent differs: {target}",
                failures,
            )

    preferences_path = codex_home / "codex-orchestration" / "preferences.toml"
    if preferences_path.exists() or path_is_link_like(preferences_path):
        if has_symlink_component(preferences_path, codex_home) or not preferences_path.is_file():
            failures.append(
                f"runtime preferences missing, linked, or conflicting: {preferences_path}"
            )
        else:
            try:
                source = preferences_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(f"runtime preferences unreadable: {preferences_path}: {error}")
            else:
                failures.extend(
                    f"runtime preferences invalid: {preferences_path}: {failure}"
                    for failure in preferences_failures(source)
                )
    routing_path = codex_home / "codex-orchestration" / "model-routing.toml"
    if routing_path.exists() or path_is_link_like(routing_path):
        if has_symlink_component(routing_path, codex_home) or not routing_path.is_file():
            failures.append(f"runtime model routing linked or conflicting: {routing_path}")
        else:
            try:
                source = routing_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(f"runtime model routing unreadable: {routing_path}: {error}")
            else:
                failures.extend(
                    f"runtime model routing invalid: {routing_path}: {failure}"
                    for failure in model_routing_failures(source, allow_placeholders=False)
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--global-rules", action="store_true")
    args = parser.parse_args()

    failures = validate_source()
    if args.runtime:
        codex_home = args.codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        if args.skills_root is None:
            parser.error("--runtime requires the active --skills-root")
        codex_home = codex_home.expanduser().absolute()
        skills_root = args.skills_root.expanduser().absolute()
        failures.extend(
            validate_runtime(
                codex_home,
                skills_root,
            )
        )
        if args.global_rules:
            failures.extend(validate_global_rules(codex_home))
    elif args.global_rules:
        parser.error("--global-rules requires --runtime")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: source contract; agents={len(WRITERS | READERS)}; target-platforms=macOS,Windows")
    if args.runtime:
        print("OK: runtime skill and agents match source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
