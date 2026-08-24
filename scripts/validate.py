#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shlex
import subprocess
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
    "frontend-design",
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
WORKER_PACKAGE_FIELDS = (
    "GOAL",
    "SCOPE",
    "CONSTRAINTS",
    "DONE WHEN",
    "RETURN",
    "WRITE LEASE: granted",
    "ALLOWED PATHS",
    "BRANCH",
    "ROUND",
    "VALIDATION",
)
FORBIDDEN_PUBLIC_PATTERNS = {
    "/" + "Users/": "absolute macOS user path",
    "C:" + "\\Users\\": "absolute Windows user path",
    "Asia" + "/Shanghai": "personal timezone",
    "xai/" + "grok": "machine-specific model route",
    "gpt-" + "5.6": "machine-specific model route",
    "deepseek-" + "v4": "machine-specific model route",
}
HOOK_REGISTRATIONS = (("SubagentStart", "subagent_scope.py", None),)
RETIRED_HOOK_SCRIPTS = ("subagent_guard.py",)
RETIRED_HOOK_SHA256 = {
    "subagent_guard.py": frozenset(
        {
            "c9f1b1cc9ee7a1bfb7db5320a1e76e9378948c5e6cba414b8408dcbaa84527fb",
            "d375ee6b67a85891765bf0c839d6616b828278e35394fc2a69cba250ea3180b1",
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
        match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*"([^"]*)"\s*$', line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


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
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent
    return boundary.is_symlink()


def first_symlink_component(path: Path) -> Path | None:
    return path if path.is_symlink() else None


def expected_hook_command(target: Path, *, windows: bool | None = None) -> str:
    arguments = [str(Path(sys.executable).absolute()), str(target.absolute())]
    use_windows = windows if windows is not None else os.name == "nt"
    if use_windows:
        return subprocess.list2cmdline(arguments)
    return shlex.join(arguments)


def hook_command_matches(command: object, target: Path, *, windows: bool | None = None) -> bool:
    if not isinstance(command, str):
        return False
    use_windows = windows if windows is not None else os.name == "nt"
    if use_windows:
        return command == expected_hook_command(target, windows=True)
    try:
        arguments = shlex.split(command, posix=True)
    except ValueError:
        return False
    return arguments == [str(Path(sys.executable).absolute()), str(target.absolute())]


def hook_command_arguments(command: object, *, windows: bool) -> list[str] | None:
    if not isinstance(command, str):
        return None
    try:
        arguments = shlex.split(command, posix=not windows)
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


def command_invokes_retired_hook(command: object, *, windows: bool) -> bool:
    """Recognize the former exact two-argument Python Hook command shape."""
    script_path = python_hook_script(command, windows=windows)
    if script_path is None:
        return False
    script = script_path.replace("\\", "/").rsplit("/", 1)[-1]
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def hook_path_key(path: str | Path, *, windows: bool) -> str:
    key = str(path).replace("\\", "/")
    return key.casefold() if windows else key


def retired_hook_failures(codex_home: Path, *, windows: bool | None = None) -> list[str]:
    """Find retired project Hook assets without claiming unrelated Hook ownership."""
    failures: list[str] = []
    use_windows = windows if windows is not None else os.name == "nt"
    hooks_root = codex_home / "hooks"
    route_target = hooks_root / "orchestration_route.py"
    if hooks_root.is_symlink() or (hooks_root.exists() and not hooks_root.is_dir()):
        failures.append(f"runtime Hook directory linked or conflicting: {hooks_root}")
    elif hooks_root.is_dir():
        for script in RETIRED_HOOK_SCRIPTS:
            target = hooks_root / script
            if target.is_symlink() or (target.exists() and not target.is_file()):
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

        if route_target.is_symlink() or (route_target.exists() and not route_target.is_file()):
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
    if not hooks_path.exists() and not hooks_path.is_symlink():
        return failures
    if hooks_path.is_symlink() or not hooks_path.is_file():
        failures.append(f"runtime hooks config linked or conflicting: {hooks_path}")
        return failures
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError) as error:
        failures.append(f"runtime hooks config invalid: {hooks_path}: {error}")
        return failures
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        failures.append(f"runtime hooks config has invalid root: {hooks_path}")
        return failures

    for event, groups in data["hooks"].items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue

            if event == "UserPromptSubmit":
                seen_route_paths: set[str] = set()
                for hook in group["hooks"]:
                    if not isinstance(hook, dict) or hook.get("type") != "command":
                        continue
                    command_fields = ((hook.get("command"), use_windows),)
                    if hook.get("commandWindows") is not None:
                        command_fields += ((hook.get("commandWindows"), True),)
                    for command, command_windows in command_fields:
                        script = python_hook_script(command, windows=command_windows)
                        if script is None:
                            continue
                        script_name = script.replace("\\", "/").rsplit("/", 1)[-1]
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
                        script_path = Path(script)
                        if script_path.is_symlink() or not script_path.is_file():
                            failures.append(
                                f"retired route registration ownership conflicts: {event}: "
                                f"{hooks_path}: {script}"
                            )
                            continue
                        try:
                            script_digest = file_sha256(script_path)
                        except OSError as error:
                            failures.append(
                                f"retired route registration unreadable: {event}: {hooks_path}: "
                                f"{script}: {error}"
                            )
                            continue
                        if script_digest in RETIRED_ROUTE_SHA256:
                            failures.append(
                                f"retired route registration remains: {event}: {hooks_path}: "
                                f"{script}"
                            )
                        else:
                            failures.append(
                                f"retired route registration ownership conflicts: {event}: "
                                f"{hooks_path}: {script}"
                            )

            matcher = group.get("matcher")
            if not isinstance(matcher, str) or (event, matcher) not in LEGACY_HOOK_GROUPS:
                continue
            for hook in group["hooks"]:
                if not isinstance(hook, dict) or hook.get("type") != "command":
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
    model_routing = (ROOT / "references" / "model-routing.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")

    require(
        top_level_values(project).get("version") == "0.6.1",
        "project version must be 0.6.1",
        failures,
    )

    for phrase in (
        "version: 0.6.1",
        "references/model-routing.md",
        "references/worker-writing.md",
        "task_package_language",
        "coverage",
        "panel",
        "hybrid",
        "Use this required core",
        "Add only the extensions that materially change the work",
        "FOCUS",
        "DELTA",
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
        "WORKSTREAM: panel | specialist",
        "Before selecting a model for any delegation",
        "`WORKSTREAM: panel` in `hybrid` use parent-aware panel routes",
        "unisolated prompt injection",
        "Do not load or execute this Skill",
        "writable-worker lease check",
    ):
        require(phrase in skill, f"missing Skill contract: {phrase}", failures)

    for phrase in (
        "latest host-generated system or developer model binding",
        "explicit `model_switch`",
        "panel_routes.gpt",
        "panel_routes.third_party",
        "fails closed to `panel_routes.gpt`",
        "WORKSTREAM: panel | specialist",
        "specialist workstreams use ordinary role routes",
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
    hook_source = (ROOT / "hooks" / "subagent_scope.py").read_text(encoding="utf-8")
    hook_roles_match = re.search(
        r"^WRITER_ROLES = frozenset\((\{[^\n]+\})\)$", hook_source, re.MULTILINE
    )
    hook_writer_roles = None
    if hook_roles_match is not None:
        try:
            hook_writer_roles = ast.literal_eval(hook_roles_match.group(1))
        except (SyntaxError, ValueError):
            pass
    require(
        hook_writer_roles == WRITERS,
        "SubagentStart Hook writer roles do not match agent contract",
        failures,
    )
    for name in WRITERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "workspace-write",
            f"{name} must be writable",
            failures,
        )
        for field in WORKER_PACKAGE_FIELDS:
            require(
                field in profile_sources.get(name, ""),
                f"{name} does not expose worker package field: {field}",
                failures,
            )
    for field in WORKER_PACKAGE_FIELDS:
        require(
            field in hook_source,
            f"SubagentStart Hook does not expose worker package field: {field}",
            failures,
        )
    require(
        "WRITER LEASE CHECK (HIGH PRIORITY)" in hook_source,
        "SubagentStart Hook lease check is not high priority",
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
        "Method-worker boundaries",
        "returns a checkpoint to the main agent",
        "never turns a prototype into production architecture",
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

    grant = "WRITE LEASE" + ": " + "granted"
    require(
        worker_contract.count(grant) == 1,
        "canonical grant literal must appear exactly once",
        failures,
    )
    for field in WORKER_PACKAGE_FIELDS:
        require(field in worker_contract, f"worker contract missing field: {field}", failures)
    require(
        "Reusing a worker thread does not extend or recreate the previous lease" in worker_contract,
        "worker contract permits implicit lease reuse",
        failures,
    )

    for hook in sorted((ROOT / "hooks").glob("*.py")):
        try:
            compile(hook.read_text(encoding="utf-8"), str(hook), "exec")
        except SyntaxError as error:
            failures.append(f"hook syntax error: {hook.name}: {error}")
    require(
        (ROOT / "skills" / "diagnosing-bugs" / "scripts" / "hitl-loop.template.ps1").is_file(),
        "Windows HITL template missing",
        failures,
    )

    for phrase in (
        "Agent installation contract",
        "Existing links are conflicts",
        "Show one complete installation plan",
        "not a managed target classification",
        "commandWindows",
        "byte-for-byte identical",
        "Preserve unrelated Skills, Agents, configuration, and files",
        "Do not register the checkout root itself as one Skill",
        "One-time migration from another source",
        "Task-package language",
        "examples/preferences.toml",
        "<codex-home>/codex-orchestration/preferences.toml",
        "--skills-root",
        "subagent_scope.py",
        "tool guard",
        "Retired lifecycle and Route assets",
        "mixed v1/v2",
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
        text = path.read_text(encoding="utf-8")
        failures.extend(public_pattern_failures(str(path.relative_to(ROOT)), text))

    require(
        (ROOT / "docs" / "adr" / "0007-pure-v2-collaboration-lifecycle.md").is_file(),
        "pure v2 collaboration ADR missing",
        failures,
    )
    for script in RETIRED_HOOK_SCRIPTS:
        require(
            not (ROOT / "hooks" / script).exists(),
            f"retired lifecycle Hook remains in source: {script}",
            failures,
        )
    require(
        not (ROOT / "hooks" / "orchestration_route.py").exists(),
        "retired main-agent Route Hook remains in source",
        failures,
    )

    require(
        not (ROOT / "scripts" / "install.py").exists(),
        "legacy write installer must not be shipped",
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
        linked = first_symlink_component(root)
        if linked is not None:
            failures.append(f"runtime {label} has linked path component: {linked}")
    if failures:
        return failures

    failures.extend(retired_hook_failures(codex_home))

    for name, source_root in BUNDLED_SKILLS.items():
        target_root = skills_root / name
        if target_root.is_symlink() or not target_root.is_dir():
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
    if agents_root.is_symlink() or not agents_root.is_dir():
        failures.append(f"runtime Agent directory missing, linked, or conflicting: {agents_root}")
    else:
        for source in sorted((ROOT / "agents").glob("*.toml")):
            target = agents_root / source.name
            require(
                not target.is_symlink() and target.is_file() and files_equal(target, source),
                f"runtime agent differs: {target}",
                failures,
            )

    preferences_path = codex_home / "codex-orchestration" / "preferences.toml"
    if preferences_path.exists() or preferences_path.is_symlink():
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
    if routing_path.exists() or routing_path.is_symlink():
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


def validate_hooks(codex_home: Path, *, windows: bool | None = None) -> list[str]:
    failures: list[str] = []
    use_windows = windows if windows is not None else os.name == "nt"
    linked = first_symlink_component(codex_home)
    if linked is not None:
        return [f"runtime Codex home has linked path component: {linked}"]
    hooks_root = codex_home / "hooks"
    if hooks_root.is_symlink() or not hooks_root.is_dir():
        return [f"runtime Hook directory missing, linked, or conflicting: {hooks_root}"]
    failures.extend(retired_hook_failures(codex_home, windows=use_windows))

    targets: list[tuple[str, Path, str | None]] = []
    for event, script, matcher in HOOK_REGISTRATIONS:
        source = ROOT / "hooks" / script
        target = hooks_root / script
        require(
            not target.is_symlink() and target.is_file() and files_equal(target, source),
            f"runtime hook differs: {target}",
            failures,
        )
        targets.append((event, target, matcher))

    hooks_path = codex_home / "hooks.json"
    if hooks_path.is_symlink() or not hooks_path.is_file():
        failures.append(f"runtime hooks config missing, linked, or conflicting: {hooks_path}")
        return failures
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError) as error:
        failures.append(f"runtime hooks config invalid: {hooks_path}: {error}")
        return failures
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        failures.append(f"runtime hooks config has invalid root: {hooks_path}")
        return failures

    for event, target, expected_matcher in targets:
        groups = data["hooks"].get(event, [])
        count = 0
        if isinstance(groups, list):
            for group in groups:
                if not isinstance(group, dict) or group.get("matcher") != expected_matcher:
                    continue
                hooks = group.get("hooks", []) if isinstance(group, dict) else []
                if not isinstance(hooks, list):
                    continue
                for hook in hooks:
                    if not isinstance(hook, dict) or hook.get("type") != "command":
                        continue
                    command = hook.get("commandWindows" if use_windows else "command")
                    if not hook_command_matches(command, target, windows=use_windows):
                        continue
                    if use_windows and not hook_command_matches(
                        hook.get("command"), target, windows=True
                    ):
                        continue
                    count += 1
        require(
            count == 1,
            f"runtime Hook registration count is {count}, expected 1: {event}: {target}",
            failures,
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--hooks", action="store_true")
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
        if args.hooks:
            failures.extend(validate_hooks(codex_home))
    elif args.hooks:
        parser.error("--hooks requires --runtime")
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
