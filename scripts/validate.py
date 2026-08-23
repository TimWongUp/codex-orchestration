#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import ast
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
HOOK_REGISTRATIONS = (
    ("UserPromptSubmit", "orchestration_route.py", None),
    ("SubagentStart", "subagent_scope.py", None),
    (
        "PreToolUse",
        "subagent_guard.py",
        r"send_input$",
    ),
    (
        "PostToolUse",
        "subagent_guard.py",
        r"wait_agent$",
    ),
)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def routing_example_failures(source: str) -> list[str]:
    """Validate the deliberately small TOML subset used by the routing example."""
    failures: list[str] = []
    top_level: dict[str, object] = {}
    overrides: list[dict[str, object]] = []
    routes: dict[str, list[dict[str, object]]] = {}
    current = top_level

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section = re.fullmatch(r"\[\[(task_overrides|roles\.([A-Za-z0-9_-]+))\]\]", line)
        if section:
            if section.group(1) == "task_overrides":
                current = {}
                overrides.append(current)
            else:
                role = section.group(2)
                current = {}
                routes.setdefault(role, []).append(current)
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if not assignment:
            failures.append(f"routing example line {line_number} is not supported TOML")
            continue
        key, raw_value = assignment.groups()
        if key in current:
            failures.append(f"routing example line {line_number} repeats {key}")
            continue
        try:
            current[key] = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError):
            failures.append(f"routing example line {line_number} has an invalid value")

    require(
        top_level == {"schema_version": 1}, "routing example schema_version is invalid", failures
    )
    allowed_roles = WRITERS | READERS | {"ROLE_NAME"}
    override_keys = {"task_kind", "roles", "model", "reasoning_effort"}
    route_keys = {"model", "reasoning_effort"}
    optional_keys = {"service_tier", "note"}

    require(bool(overrides), "routing example has no task override", failures)
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

    require(bool(routes), "routing example has no role routes", failures)
    for role, entries in routes.items():
        require(role in allowed_roles, f"routing example has unknown role: {role}", failures)
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

    for entry in overrides + [item for entries in routes.values() for item in entries]:
        model = entry.get("model")
        require(
            isinstance(model, str) and model.startswith("MODEL_ID_"),
            "routing example contains a non-placeholder model",
            failures,
        )
        require(
            isinstance(entry.get("reasoning_effort"), str),
            "routing example has an invalid reasoning_effort",
            failures,
        )
    return failures


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
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")

    require(
        top_level_values(project).get("version") == "0.5.2",
        "project version must be 0.5.2",
        failures,
    )

    for phrase in (
        "version: 0.5.2",
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
        "Reusing a thread does not extend or recreate a write lease",
        "Single writer",
        "Do not create a worktree unless the user explicitly requests one",
        "timed_out=true",
        "exactly one lifecycle call per program",
        "Do not interrupt, close, replace, or switch the model",
        "matching local task override",
        "unisolated prompt injection",
        "same effective route",
        "Do not load or execute this Skill",
        "ORCHESTRATOR_CORRECTION:",
        "<reason_code>",
        "control envelope",
        "exactly one control prefix",
        "sole text carrier",
        "interrupt=true",
        "wrong_model",
        "may terminate",
        "runtime/UI resolved-model metadata",
        "resolved model",
        "unknown`/unconfirmed",
    ):
        require(phrase in skill, f"missing Skill contract: {phrase}", failures)

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
        "HIGH PRIORITY DERIVED-AGENT IDENTITY" in hook_source,
        "SubagentStart Hook identity context is not high priority",
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
    guard_source = (ROOT / "hooks" / "subagent_guard.py").read_text(encoding="utf-8")
    for phrase in (
        "USER_REQUESTED_INTERRUPT:",
        "ORCHESTRATOR_CORRECTION:",
        "permissionDecision",
        "appear exactly once",
        "sole text carrier",
        "requires interrupt=true",
        "WAIT RESULT CHECK",
    ):
        require(phrase in guard_source, f"subagent guard missing contract: {phrase}", failures)
    require(
        "terminal-marker" not in guard_source and "terminal marker" not in guard_source,
        "subagent guard must not enforce terminal markers",
        failures,
    )
    require(
        "_marker" not in guard_source,
        "subagent guard must not enforce close ordering",
        failures,
    )
    for event, _script, matcher in HOOK_REGISTRATIONS:
        if matcher is None:
            continue
        pattern = re.compile(matcher)
        tools = ("send_input",) if event == "PreToolUse" else ("wait_agent",)
        for tool in tools:
            for candidate in (
                tool,
                f"multi_agent_v1{tool}",
                f"multi_agent_v1__{tool}",
                f"multi_agent_v1.{tool}",
            ):
                require(
                    pattern.search(candidate) is not None,
                    f"{event} matcher misses supported tool name: {candidate}",
                    failures,
                )
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
        "send_input$",
        "wait_agent$",
        "does not enforce close ordering",
        "no registration invokes this",
        "does not confirm the resolved model",
    ):
        require(phrase in install_contract, f"missing install contract: {phrase}", failures)

    for phrase in (
        "may add advisory context for a",
        "four closed reason codes",
        "does not persist terminal state",
        "`close_agent`",
        "responsible for evidence, bounded correction use",
        "does not confirm the resolved model",
    ):
        require(
            phrase in configuration,
            f"configuration missing current guard contract: {phrase}",
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
        (ROOT / "docs" / "adr" / "0006-use-a-stateless-subagent-interrupt-guard.md").is_file(),
        "stateless interrupt guard ADR missing",
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
    for phrase in ("effective route", "first candidate, not a hard pin"):
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
                and target.read_bytes() == source.read_bytes(),
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
                not target.is_symlink()
                and target.is_file()
                and target.read_bytes() == source.read_bytes(),
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

    targets: list[tuple[str, Path, str | None]] = []
    for event, script, matcher in HOOK_REGISTRATIONS:
        source = ROOT / "hooks" / script
        target = hooks_root / script
        require(
            not target.is_symlink()
            and target.is_file()
            and target.read_bytes() == source.read_bytes(),
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

    guard_target = hooks_root / "subagent_guard.py"
    for event, groups in data["hooks"].items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher")
            hooks = group.get("hooks", [])
            if not isinstance(hooks, list):
                continue
            for hook in hooks:
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    continue
                fields = ("command", "commandWindows") if use_windows else ("command",)
                invokes_guard = any(
                    hook_command_matches(hook.get(field), guard_target, windows=use_windows)
                    for field in fields
                )
                allowed_guard_registration = (event, matcher) in {
                    ("PreToolUse", r"send_input$"),
                    ("PostToolUse", r"wait_agent$"),
                }
                if invokes_guard and not allowed_guard_registration:
                    failures.append(
                        "runtime stale managed guard registration: "
                        f"{event}: matcher={matcher!r}: {guard_target}"
                    )

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
