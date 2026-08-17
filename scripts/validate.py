#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
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
FORBIDDEN_PUBLIC_PATTERNS = {
    "/" + "Users/": "absolute macOS user path",
    "C:" + "\\Users\\": "absolute Windows user path",
    "Asia" + "/Shanghai": "personal timezone",
    "xai/" + "grok": "machine-specific model route",
    "gpt-" + "5.6": "machine-specific model route",
    "deepseek-" + "v4": "machine-specific model route",
}


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


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


def expected_hook_command(target: Path) -> str:
    arguments = [str(Path(sys.executable).absolute()), str(target.absolute())]
    if os.name == "nt":
        return subprocess.list2cmdline(arguments)
    return shlex.join(arguments)


def hook_command_matches(command: object, target: Path) -> bool:
    if not isinstance(command, str):
        return False
    if os.name == "nt":
        return command == expected_hook_command(target)
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


def validate_source() -> list[str]:
    failures: list[str] = []
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    install_contract = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    worker_contract = (ROOT / "references" / "worker-writing.md").read_text(encoding="utf-8")

    for phrase in (
        "version: 0.3.0",
        "references/model-routing.md",
        "references/worker-writing.md",
        "coverage",
        "panel",
        "hybrid",
        "Single writer",
        "Do not create a worktree unless the user explicitly requests one",
        "A wait timeout means only",
        "Do not interrupt, close, replace, or switch the model",
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
    for path in sorted((ROOT / "agents").glob("*.toml")):
        source = path.read_text(encoding="utf-8")
        values = top_level_values(source)
        name = values.get("name")
        require(name is not None, f"missing agent name: {path.name}", failures)
        if name:
            profiles[name] = values
            require(name == path.stem, f"agent filename/name mismatch: {path.name}", failures)
        pinned = FORBIDDEN_KEYS.intersection(values)
        require(not pinned, f"agent pins model settings: {path.name}: {sorted(pinned)}", failures)
    require(set(profiles) == WRITERS | READERS, "agent role set does not match contract", failures)
    for name in WRITERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "workspace-write",
            f"{name} must be writable",
            failures,
        )
    for name in READERS:
        require(
            profiles.get(name, {}).get("sandbox_mode") == "read-only",
            f"{name} must be read-only",
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

    grant = "WRITE LEASE" + ": " + "granted"
    require(
        worker_contract.count(grant) == 1,
        "canonical grant literal must appear exactly once",
        failures,
    )
    for field in (
        "GOAL",
        "SCOPE",
        "CONSTRAINTS",
        "DONE WHEN",
        "RETURN",
        "ALLOWED PATHS",
        "BRANCH",
        "ROUND",
        "VALIDATION",
    ):
        require(field in worker_contract, f"worker contract missing field: {field}", failures)

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
        "commandWindows",
        "Preserve unrelated Skills, Agents, configuration, and files",
        "--skills-root",
    ):
        require(phrase in install_contract, f"missing install contract: {phrase}", failures)

    for path in public_text_files():
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_PUBLIC_PATTERNS.items():
            require(pattern not in text, f"{label} in {path.relative_to(ROOT)}", failures)

    require(
        not (ROOT / "scripts" / "install.py").exists(),
        "legacy write installer must not be shipped",
        failures,
    )
    require(
        "MODEL_ID_PRIMARY"
        in (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8"),
        "routing example lost placeholders",
        failures,
    )
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
    return failures


def validate_hooks(codex_home: Path) -> list[str]:
    failures: list[str] = []
    linked = first_symlink_component(codex_home)
    if linked is not None:
        return [f"runtime Codex home has linked path component: {linked}"]
    hooks_root = codex_home / "hooks"
    if hooks_root.is_symlink() or not hooks_root.is_dir():
        return [f"runtime Hook directory missing, linked, or conflicting: {hooks_root}"]

    targets: dict[str, Path] = {}
    for event, script in {
        "UserPromptSubmit": "orchestration_route.py",
        "SubagentStart": "subagent_scope.py",
    }.items():
        source = ROOT / "hooks" / script
        target = hooks_root / script
        require(
            not target.is_symlink()
            and target.is_file()
            and target.read_bytes() == source.read_bytes(),
            f"runtime hook differs: {target}",
            failures,
        )
        targets[event] = target

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

    command_field = "commandWindows" if os.name == "nt" else "command"
    for event, target in targets.items():
        groups = data["hooks"].get(event, [])
        count = 0
        if isinstance(groups, list):
            for group in groups:
                hooks = group.get("hooks", []) if isinstance(group, dict) else []
                if not isinstance(hooks, list):
                    continue
                for hook in hooks:
                    if not isinstance(hook, dict) or hook.get("type") != "command":
                        continue
                    command = hook.get(command_field)
                    if hook_command_matches(command, target):
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
