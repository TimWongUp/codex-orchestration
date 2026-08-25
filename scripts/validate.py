#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import ntpath
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REVISION = "8b78b531ab965735c5dc74f6f7a219e1e37326df"
BUNDLED_SKILLS = {
    "codex-orchestration": ROOT,
    "diagnosing-bugs": ROOT / "skills" / "diagnosing-bugs",
    "prototype": ROOT / "skills" / "prototype",
}
WRITERS = {"worker", "diagnosing-bugs-worker", "prototype-worker"}
READERS = {
    "default",
    "explorer",
    "reference-researcher",
    "web-researcher",
    "correctness-reviewer",
    "architecture-reviewer",
    "security-reviewer",
    "performance-reviewer",
    "test-reliability-reviewer",
    "specialist-reviewer",
    "adversarial-verifier",
    "expert",
}
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
    "R0-R3 review gate against the combined diff",
    "Lane review never substitutes for the integrated review",
    "Stop convergence",
    "A stopped batch is not",
)
WORKTREE_INTEGRATION_SEQUENCE = (
    "The Integration Root waits for the complete batch",
    "Serially merges accepted branches into a dedicated integration branch",
    "Runs the combined validation after all accepted branches are present",
    "Selects and completes the R0-R3 review gate against the combined diff",
)
WORKTREE_ADR_PHRASES = (
    "at most three nonterminal Worktree Roots",
    "normal local orchestration authority",
    "verified distinct official",
    "Failed or canceled lanes",
    "user's explicit rescoping",
    "Prototype lanes",
    "final R0-R3 review gate",
    "at most eight spawned-agent threads",
    "Explicit stop freezes",
    "no batch has more than three concurrent repository writers",
)
WORKTREE_ADR_SEQUENCE = (
    "waits for every declared handoff to reach `accepted`",
    "serially merges lanes into a dedicated integration branch",
    "runs combined validation",
    "applies the final R0-R3 review gate",
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
RETIRED_HOOK_SCRIPTS = ("subagent_guard.py", "subagent_scope.py")
RETIRED_AGENT_SHA256 = {
    "frontend-design.toml": frozenset(
        {
            "2187c665f79641d5c2fcc7bf9e6ebe1ae779546b725bfc49de38e544ceb65b56",
            "4a944a23e66c4237e4925c3961727db3cc1fe62fbc4ba8cadd8900875b867192",
            "c1ffa1f1dd435f6936314c18710ff8266ed6df4d6b00b18c1564f6253b039c06",
            "c8d6537150fca80f825469e2821d30bb9109ac68f8746db2127e012f94c30080",
        }
    )
}
RETIRED_HOOK_SHA256 = {
    "subagent_guard.py": frozenset(
        {
            "c9f1b1cc9ee7a1bfb7db5320a1e76e9378948c5e6cba414b8408dcbaa84527fb",
            "d375ee6b67a85891765bf0c839d6616b828278e35394fc2a69cba250ea3180b1",
        }
    ),
    "subagent_scope.py": frozenset(
        {
            "390c3066a1caa60068b14fba1f67bc5c7854aa0fa4a1b017538deac9c070faad",
            "458600a69747d6394103190e0b560e4cc82dfcca191e03ca1aa96afab72702ca",
            "486165ed2b326497f7785a0bc2cd05d537d5e8e2129f76ade784e4ed69635b7c",
            "760a2f2e9562a7cb10ae9838391ed114e8a60423b06aaeb96792034ac0603727",
            "9a14a6bf39dcf0d44edc6f6946a74094febd1db6f9a41c7ea2da108582c96d9b",
            "c1ce7dbae26be92ba359a52082e94d1041625cc79cc0c3c4a9070e55b0ba71aa",
            "fa82cf03d992b374cf21e323e3d1f42326995b2fae8941fa10c8e0645091a2ce",
            "ff3ef1b1f18f5e1b99712c8fde518c343b920abf4f68ba0569f4fb7e1f4b9930",
        }
    ),
}
LEGACY_V1_ROUTE_SHA256 = frozenset(
    {
        "67f95392bb8e96460a5b30b4295e31a2e81643ed75c5ef5c216390e6ef557dcf",
        "bdbacc28beb7c081db9d85e82d85ddadde259058a16ea2084f02ee361575c561",
    }
)
KNOWN_PRIOR_V2_ROUTE_SHA256 = frozenset(
    {
        "060848145efd4639999a16cd2fe5987ff0e7187e794f7aa7a42057a91ce2cc54",
        "ce1979fb2c88f5a8449c9e31e00d0d9ea5e0d136d87aed5d244a89dd65fd6503",
    }
)
RETIRED_ROUTE_SHA256 = LEGACY_V1_ROUTE_SHA256 | KNOWN_PRIOR_V2_ROUTE_SHA256
LEGACY_HOOK_GROUPS = frozenset(
    {
        ("PreToolUse", r"send_input$"),
        ("PreToolUse", r"close_agent$"),
        ("PreToolUse", r"send_input$|close_agent$"),
        ("PostToolUse", r"wait_agent$"),
        ("PostToolUse", r"(?:functions[._]?exec|wait_agent)$"),
    }
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
    require(project_version == "0.8.0", "project version must be 0.8.0", failures)
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
            "combined validation, then R0-R3 review",
            failures,
        )
    return failures


def worktree_adr_failures(source: str) -> list[str]:
    failures: list[str] = []
    normalized = re.sub(r"\s+", " ", source)
    for phrase in WORKTREE_ADR_PHRASES:
        require(phrase in normalized, f"worktree-root ADR missing decision: {phrase}", failures)
    positions = [normalized.find(marker) for marker in WORKTREE_ADR_SEQUENCE]
    for marker, position in zip(WORKTREE_ADR_SEQUENCE, positions):
        require(position >= 0, f"worktree-root ADR missing sequence: {marker}", failures)
    if all(position >= 0 for position in positions):
        require(
            positions == sorted(set(positions)),
            "worktree-root ADR sequence must be accepted batch, serial merge, combined "
            "validation, then final R0-R3 review",
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


def expected_hook_command(target: Path, *, windows: bool | None = None) -> str:
    arguments = [str(Path(sys.executable).absolute()), str(target.absolute())]
    use_windows = windows if windows is not None else os.name == "nt"
    if use_windows:
        return " ".join(f'"{argument}"' for argument in arguments)
    return shlex.join(arguments)


def hook_command_arguments(command: object, *, windows: bool) -> list[str] | None:
    if not isinstance(command, str):
        return None
    if windows:
        command = re.sub(r"\^(?:\r\n|\n|\r)", "", command)
    else:
        command = re.sub(r"\\(?:\r\n|\n|\r)", "", command)
    try:
        lexer = shlex.shlex(command, posix=not windows, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        arguments = list(lexer)
    except ValueError:
        return None
    if windows:
        arguments = [
            argument[1:-1]
            if len(argument) >= 2 and argument[0] == argument[-1] == '"'
            else argument
            for argument in arguments
        ]
    return arguments


def unparseable_command_mentions_retired_hook(command: object, *, windows: bool) -> bool:
    if not isinstance(command, str) or hook_command_arguments(command, windows=windows) is not None:
        return False
    value = command.casefold() if windows or sys.platform == "darwin" else command
    names = {
        name.casefold() if windows or sys.platform == "darwin" else name
        for name in (*RETIRED_HOOK_SCRIPTS, "orchestration_route.py")
    }
    return any(name in value for name in names)


def command_invokes_retired_hook(command: object, *, windows: bool) -> bool:
    """Recognize the former exact two-argument Python Hook command shape."""
    script_path = python_hook_script(command, windows=windows)
    if script_path is None:
        return False
    script = script_path.replace("\\", "/").rsplit("/", 1)[-1].split("\0", 1)[0]
    if windows:
        script = script.casefold()
        retired = {name.casefold() for name in RETIRED_HOOK_SCRIPTS}
    else:
        retired = set(RETIRED_HOOK_SCRIPTS)
    return script in retired


def python_hook_script(command: object, *, windows: bool) -> str | None:
    """Return the script argument from an exact two-argument Python Hook command."""
    arguments = hook_command_arguments(command, windows=windows)
    if arguments is None or len(arguments) != 2:
        return None
    executable = arguments[0].replace("\\", "/").rsplit("/", 1)[-1]
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable, re.IGNORECASE) is None:
        return None
    return arguments[1]


def python_invoked_script(command: object, *, windows: bool) -> str | None:
    """Find a Python script after interpreter options for fail-closed reference checks."""
    arguments = hook_command_arguments(command, windows=windows)
    if arguments is None or len(arguments) < 2:
        return None
    index = 0
    assignment = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.DOTALL)
    if not windows:
        while index < len(arguments) and assignment.fullmatch(arguments[index]) is not None:
            index += 1
        if index < len(arguments):
            executable = arguments[index].replace("\\", "/").rsplit("/", 1)[-1]
            if executable == "env":
                index += 1
                env_options_with_value = {"-u", "--unset", "-C", "--chdir"}
                while index < len(arguments):
                    argument = arguments[index]
                    if argument == "--":
                        index += 1
                        break
                    if argument in env_options_with_value:
                        index += 2
                        continue
                    if argument.startswith("-"):
                        index += 1
                        continue
                    if assignment.fullmatch(argument) is not None:
                        index += 1
                        continue
                    break
    if index >= len(arguments):
        return None
    executable = arguments[index].replace("\\", "/").rsplit("/", 1)[-1]
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable, re.IGNORECASE) is None:
        return None
    index += 1
    options_with_value = {"-W", "-X", "--check-hash-based-pycs"}
    while index < len(arguments):
        argument = arguments[index]
        if argument in {"-c", "-m", "-"}:
            return None
        if argument == "--":
            return arguments[index + 1] if index + 1 < len(arguments) else None
        if argument in options_with_value:
            index += 2
            continue
        if argument.startswith("-"):
            index += 1
            continue
        return argument
    return None


def command_path_candidates(command: object, *, windows: bool) -> list[str]:
    """Find explicit or nested absolute paths plus a parsed Python script argument."""
    candidates: list[str] = []

    def add(candidate: str) -> None:
        if candidate not in candidates:
            candidates.append(candidate)

    invoked = python_invoked_script(command, windows=windows)
    if invoked is not None:
        add(invoked)
    arguments = hook_command_arguments(command, windows=windows)
    if arguments is None:
        return candidates
    path_module = ntpath if windows else posixpath
    for argument in arguments:
        if path_module.isabs(argument):
            add(argument)
        for quoted in re.findall(r"(['\"])(.*?)\1", argument):
            candidate = quoted[1]
            if path_module.isabs(candidate):
                add(candidate)
        if not windows and any(character.isspace() for character in argument):
            nested = hook_command_arguments(argument, windows=False)
            if nested is None or nested == [argument]:
                continue
            nested_invoked = python_invoked_script(argument, windows=False)
            if nested_invoked is not None:
                add(nested_invoked)
            for nested_argument in nested:
                if posixpath.isabs(nested_argument):
                    add(nested_argument)
    return candidates


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def strict_json_loads(source: str | bytes) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant: {value}")

    return json.loads(
        source,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


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


def hook_path_key(path: str | Path, *, windows: bool) -> str:
    path_value = str(path)
    if windows == (os.name == "nt"):
        parsed = Path(path_value)
        if parsed.is_absolute() and ".." not in parsed.parts:
            path_value = str(canonical_selected_root(parsed))
    key = path_value.replace("\\", "/")
    return key.casefold() if windows else key


def hook_path_has_parent_traversal(path: str | Path) -> bool:
    return ".." in str(path).replace("\\", "/").split("/")


def hook_path_is_ambiguous(path: str | Path, *, windows: bool) -> bool:
    value = str(path)
    path_module = ntpath if windows else posixpath
    expansion_characters = "%!^&|<>" if windows else "$`*?[{}"
    return (
        "\0" in value
        or hook_path_has_parent_traversal(value)
        or not path_module.isabs(value)
        or any(character in value for character in expansion_characters)
    )


def hook_paths_may_alias(left: str | Path, right: str | Path, *, windows: bool) -> bool:
    left_key = hook_path_key(left, windows=windows)
    right_key = hook_path_key(right, windows=windows)
    if left_key == right_key:
        return True
    if windows == (os.name == "nt"):
        for source, target_key in ((left, right_key), (right, left_key)):
            source_path = Path(source)
            if not path_is_link_like(source_path):
                continue
            try:
                link_value = Path(os.readlink(source_path))
            except OSError:
                continue
            if not link_value.is_absolute():
                link_value = source_path.parent / link_value
            link_key = hook_path_key(link_value.resolve(strict=False), windows=windows)
            if link_key == target_key or (
                sys.platform == "darwin"
                and not windows
                and link_key.casefold() == target_key.casefold()
            ):
                return True
        try:
            if os.path.samefile(left, right):
                return True
        except (OSError, ValueError):
            pass
    return sys.platform == "darwin" and not windows and left_key.casefold() == right_key.casefold()


def referenced_script_has_retired_hash(path: str | Path, *, windows: bool) -> bool:
    if windows != (os.name == "nt") or hook_path_is_ambiguous(path, windows=windows):
        return False
    try:
        candidate = Path(path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    if not candidate.is_file():
        return False
    try:
        digest = file_sha256(candidate)
    except OSError:
        return False
    retired_hashes = set(RETIRED_ROUTE_SHA256)
    for hashes in RETIRED_HOOK_SHA256.values():
        retired_hashes.update(hashes)
    return digest in retired_hashes


def retired_hook_failures(codex_home: Path, *, windows: bool | None = None) -> list[str]:
    """Find retired project Hook assets without claiming unrelated Hook ownership."""
    failures: list[str] = []
    if path_is_link_like(codex_home):
        return [f"runtime Codex home linked or conflicting: {codex_home}"]
    linked = first_symlink_component(codex_home)
    if linked is not None:
        return [f"runtime Codex home has linked or unsafe path component: {linked}"]
    codex_home = canonical_selected_root(codex_home)
    use_windows = windows if windows is not None else os.name == "nt"
    hooks_root = codex_home / "hooks"
    route_target = hooks_root / "orchestration_route.py"
    if path_is_link_like(hooks_root) or (hooks_root.exists() and not hooks_root.is_dir()):
        failures.append(f"runtime Hook directory linked or conflicting: {hooks_root}")
    elif hooks_root.is_dir():
        for script in RETIRED_HOOK_SCRIPTS:
            target = hooks_root / script
            if path_is_link_like(target) or (target.exists() and not target.is_file()):
                failures.append(f"retired Hook path conflicts: {target}")
            elif target.is_file():
                try:
                    digest = file_sha256(target)
                except OSError as error:
                    failures.append(f"retired Hook path unreadable: {target}: {error}")
                    continue
                if digest in RETIRED_HOOK_SHA256[script]:
                    failures.append(f"retired managed hook remains: {target}")
                else:
                    failures.append(f"retired Hook path ownership conflicts: {target}")

        if path_is_link_like(route_target) or (
            route_target.exists() and not route_target.is_file()
        ):
            failures.append(f"retired route path conflicts: {route_target}")
        elif route_target.is_file():
            try:
                route_digest = file_sha256(route_target)
            except OSError as error:
                failures.append(f"retired route unreadable: {route_target}: {error}")
            else:
                if route_digest in RETIRED_ROUTE_SHA256:
                    failures.append(f"retired managed route remains: {route_target}")
                else:
                    failures.append(f"retired route path ownership conflicts: {route_target}")

    hooks_path = codex_home / "hooks.json"
    if not hooks_path.exists() and not path_is_link_like(hooks_path):
        return failures
    if path_is_link_like(hooks_path) or not hooks_path.is_file():
        failures.append(f"runtime hooks config linked or conflicting: {hooks_path}")
        return failures
    try:
        data = strict_json_loads(hooks_path.read_bytes())
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
        failures.append(f"runtime hooks config invalid: {hooks_path}: {error}")
        return failures
    if not isinstance(data, dict):
        failures.append(f"runtime hooks config has invalid root: {hooks_path}")
        return failures
    hooks_value = data.get("hooks", {})
    if not isinstance(hooks_value, dict):
        failures.append(f"runtime hooks config has invalid root: {hooks_path}")
        return failures

    seen_managed_retired_references: set[tuple[str, str]] = set()
    retired_targets = tuple(hooks_root / name for name in RETIRED_HOOK_SCRIPTS) + (route_target,)
    for event, groups in hooks_value.items():
        if not isinstance(groups, list):
            failures.append(f"runtime hooks config event must be a list: {event}: {hooks_path}")
            continue
        for group in groups:
            if not isinstance(group, dict):
                failures.append(
                    f"runtime hooks config group must be an object: {event}: {hooks_path}"
                )
                continue
            if not isinstance(group.get("hooks"), list):
                failures.append(
                    f"runtime hooks config group hooks must be a list: {event}: {hooks_path}"
                )
                continue

            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    continue
                present_fields = [
                    hook[field] for field in ("command", "commandWindows") if field in hook
                ]
                if hook.get("type") == "command" and (
                    not present_fields
                    or any(
                        not isinstance(field, str) or not field.strip() for field in present_fields
                    )
                ):
                    failures.append(
                        f"runtime command Hook has invalid command fields: {event}: {hooks_path}"
                    )
                command_fields = ((hook.get("command"), use_windows),)
                if hook.get("commandWindows") is not None:
                    command_fields += ((hook.get("commandWindows"), True),)
                for command, command_windows in command_fields:
                    if unparseable_command_mentions_retired_hook(command, windows=command_windows):
                        failures.append(
                            f"retired-looking Hook registration has unparseable command: "
                            f"{event}: {hooks_path}"
                        )
                        continue
                    for script in command_path_candidates(command, windows=command_windows):
                        script_name = script.replace("\\", "/").rsplit("/", 1)[-1].split("\0", 1)[0]
                        if command_windows or sys.platform == "darwin":
                            script_name = script_name.casefold()
                        retired_names = {
                            name.casefold() if command_windows or sys.platform == "darwin" else name
                            for name in (*RETIRED_HOOK_SCRIPTS, "orchestration_route.py")
                        }
                        if script_name in retired_names and hook_path_is_ambiguous(
                            script, windows=command_windows
                        ):
                            failures.append(
                                f"retired-looking Hook registration has unsafe path: {event}: "
                                f"{hooks_path}: {script}"
                            )
                            continue
                        if referenced_script_has_retired_hash(script, windows=command_windows):
                            failures.append(
                                f"retired project Hook code registration remains: {event}: "
                                f"{hooks_path}: {script}"
                            )
                            continue
                        script_key = hook_path_key(script, windows=command_windows)
                        if not any(
                            hook_paths_may_alias(script, target, windows=command_windows)
                            for target in retired_targets
                        ):
                            continue
                        reference_key = (event, script_key)
                        if reference_key in seen_managed_retired_references:
                            continue
                        seen_managed_retired_references.add(reference_key)
                        failures.append(
                            f"retired managed Hook registration remains: {event}: "
                            f"{hooks_path}: {script}"
                        )

            if event == "SubagentStart" and group.get("matcher") is None:
                seen_scope_paths: set[str] = set()
                for hook in group["hooks"]:
                    if not isinstance(hook, dict):
                        continue
                    command_fields = ((hook.get("command"), use_windows),)
                    if hook.get("commandWindows") is not None:
                        command_fields += ((hook.get("commandWindows"), True),)
                    for command, command_windows in command_fields:
                        script = python_hook_script(command, windows=command_windows)
                        if script is None:
                            continue
                        script_name = script.replace("\\", "/").rsplit("/", 1)[-1].split("\0", 1)[0]
                        expected_name = "subagent_scope.py"
                        if command_windows or sys.platform == "darwin":
                            script_name = script_name.casefold()
                            expected_name = expected_name.casefold()
                        if script_name != expected_name:
                            continue
                        script_key = hook_path_key(script, windows=command_windows)
                        if script_key in seen_scope_paths:
                            continue
                        seen_scope_paths.add(script_key)
                        scope_target = hooks_root / "subagent_scope.py"
                        if hook_paths_may_alias(script, scope_target, windows=command_windows):
                            failures.append(
                                f"retired scope registration remains: {event}: {hooks_path}: "
                                f"{script}"
                            )
                            continue
                        failures.append(
                            f"retired scope registration ownership conflicts: {event}: "
                            f"{hooks_path}: {script}"
                        )

            if event == "UserPromptSubmit" and group.get("matcher") is None:
                seen_route_paths: set[str] = set()
                for hook in group["hooks"]:
                    if not isinstance(hook, dict):
                        continue
                    command_fields = ((hook.get("command"), use_windows),)
                    if hook.get("commandWindows") is not None:
                        command_fields += ((hook.get("commandWindows"), True),)
                    for command, command_windows in command_fields:
                        script = python_hook_script(command, windows=command_windows)
                        if script is None:
                            continue
                        script_name = script.replace("\\", "/").rsplit("/", 1)[-1].split("\0", 1)[0]
                        if (script_name.casefold() if command_windows else script_name) != (
                            "orchestration_route.py"
                        ):
                            continue
                        script_key = hook_path_key(script, windows=command_windows)
                        if script_key in seen_route_paths:
                            continue
                        seen_route_paths.add(script_key)
                        managed_key = hook_path_key(route_target, windows=command_windows)
                        if script_key == managed_key:
                            failures.append(
                                f"retired route registration remains: {event}: {hooks_path}: "
                                f"{script}"
                            )
                            continue
                        failures.append(
                            f"retired route registration ownership conflicts: {event}: "
                            f"{hooks_path}: {script}"
                        )

            matcher = group.get("matcher")
            if not isinstance(matcher, str) or (event, matcher) not in LEGACY_HOOK_GROUPS:
                continue
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    continue
                if command_invokes_retired_hook(
                    hook.get("command"), windows=use_windows
                ) or command_invokes_retired_hook(hook.get("commandWindows"), windows=True):
                    failures.append(
                        f"retired v1-shaped hook registration remains: {event}: {hooks_path}"
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
    install_contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    worker_contract = (ROOT / "references" / "worker-writing.md").read_text(encoding="utf-8")
    worktree_contract = read_required_text(
        ROOT / "references" / "worktree-roots.md", "worktree-root contract", failures
    )
    worktree_adr = read_required_text(
        ROOT / "docs" / "adr" / "0009-coordinate-independent-worktree-roots.md",
        "worktree-root ADR",
        failures,
    )
    model_routing = (ROOT / "references" / "model-routing.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")

    failures.extend(source_version_failures(project, skill))

    for phrase in (
        "references/model-routing.md",
        "references/worker-writing.md",
        "references/worktree-roots.md",
        "task_package_language",
        "coverage",
        "panel",
        "hybrid",
        "compact brief usually",
        "headings are optional",
        "temporary handoff document",
        "same-thread follow-up",
        "No prior lease is extended",
        "Single writer",
        "Do not create a worktree unless the user explicitly requests one",
        'fork_turns="none"',
        "followup_task",
        "interrupt_agent",
        "collaboration-tool schemas are the sole authority",
        "dependency barrier",
        "earlier final notification",
        "fresh agent-tree snapshot",
        "Do not send guidance, interrupt, replace, or switch the model",
        "semantic instructions, not required labels",
        "Before selecting a model for any delegation",
        "panel workstream in `hybrid` use parent-aware panel routes",
        "unisolated prompt injection",
        "Do not load or execute this Skill",
        "Missing labels never make an",
        "Independent Worktree Roots",
        "at most three nonterminal lane slots",
        "same local orchestration authority as any other",
        "Integration Root remains\nrepository-read-only",
    ):
        require(phrase in skill, f"missing Skill contract: {phrase}", failures)

    failures.extend(worktree_contract_failures(worktree_contract))
    failures.extend(worktree_adr_failures(worktree_adr))

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
        bundled = (path / "SKILL.md").read_text(encoding="utf-8")
        require(
            skill_document_name(bundled) == name,
            f"bundled Skill name mismatch: {name}",
            failures,
        )
        if name != "codex-orchestration":
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
    for path in sorted((ROOT / "agents").glob("*.toml")):
        source = path.read_text(encoding="utf-8")
        values = top_level_values(source)
        name = values.get("name")
        require(name is not None, f"missing agent name: {path.name}", failures)
        if name:
            profiles[name] = values
            profile_sources[name] = source
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
    for name in READERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "read-only",
            f"{name} must be read-only",
            failures,
        )
    derived_identity = (
        "Do not load or execute the codex-orchestration Skill",
        "do not create, coordinate, wait for, or manage descendants",
        "panel member",
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
    for phrase in (
        "Method workers",
        "returns a checkpoint instead of guessing",
        "without turning it into production architecture",
    ):
        require(
            phrase in worker_contract,
            f"worker contract missing method boundary: {phrase}",
            failures,
        )
    require(
        "Community popularity is not proof of correctness"
        in (ROOT / "agents" / "web-researcher.toml").read_text(encoding="utf-8"),
        "web-researcher lost evidence hierarchy",
        failures,
    )

    for phrase in (
        "compact natural-language brief, not a required form",
        "Optional headings",
        "recover ordinary implementation context",
        "necessary adjacent files",
        "Do not create a temporary handoff file",
        "follow-up to the same worker thread may contain only",
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
        "Deterministic installation contract",
        "`scripts/install.py` is the only write implementation",
        "dry run",
        "`--apply`",
        "`--language en` or `--language zh-CN`",
        "CODEX-ORCHESTRATION:GLOBAL-RULES",
        "AGENTS.override.md",
        "byte-for-byte",
        "commandWindows",
        "preserves unrelated top-level fields, events, matcher groups, handlers, and order",
        "Do not register the repository root as one Skill",
        "one-time migration from links or a different checkout",
        "examples/preferences.toml",
        "--skills-root",
        "Retired project Agent and Hook assets",
        "Pure v2 verification",
        "caught write or verification failure",
        "abrupt process termination",
        "does not confirm the resolved model",
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
    ):
        require(
            phrase in configuration,
            f"configuration missing current v2 lifecycle contract: {phrase}",
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
    for script in RETIRED_HOOK_SCRIPTS:
        require(
            not os.path.lexists(ROOT / "hooks" / script),
            f"retired lifecycle Hook remains in source: {script}",
            failures,
        )
    require(
        not os.path.lexists(ROOT / "hooks" / "orchestration_route.py"),
        "retired main-agent Route Hook remains in source",
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
            "independent Worktree Roots",
            "neither the Integration Root nor its local workers write the repository",
            "at most three nonterminal lanes",
            "Each root task has one active writer",
            "derived agents never orchestrate descendants",
        ):
            require(
                phrase in decoded_global_rules,
                f"global rules missing worktree-root contract: {phrase}",
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

    failures.extend(retired_hook_failures(codex_home))

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
        for filename, known_hashes in RETIRED_AGENT_SHA256.items():
            target = agents_root / filename
            if not os.path.lexists(target):
                continue
            if path_is_link_like(target) or not target.is_file():
                failures.append(f"runtime retired Agent linked or conflicting: {target}")
                continue
            try:
                digest = file_sha256(target)
            except OSError as error:
                failures.append(f"runtime retired Agent unreadable: {target}: {error}")
            else:
                require(
                    digest not in known_hashes,
                    f"runtime retired project Agent remains: {target}",
                    failures,
                )
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
