#!/usr/bin/env python3
"""Install or inspect codex-orchestration in a macOS Codex home."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "codex-orchestration"
BUNDLED_SKILLS = {
    SKILL_NAME: ROOT,
    "diagnosing-bugs": ROOT / "skills" / "diagnosing-bugs",
    "prototype": ROOT / "skills" / "prototype",
}
HOOK_SPECS = {
    "UserPromptSubmit": "orchestration_route.py",
    "SubagentStart": "subagent_scope.py",
}


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_symlink(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        temporary.symlink_to(source, target_is_directory=True)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def parent_directory_available(target: Path) -> bool:
    parent = target.parent
    while not os.path.lexists(parent):
        if parent == parent.parent:
            return False
        parent = parent.parent
    return parent.is_dir()


def file_status(source: Path, target: Path) -> str:
    if not os.path.lexists(target):
        return "missing" if parent_directory_available(target) else "conflict"
    if not target.is_file():
        return "conflict"
    return "current" if source.read_bytes() == target.read_bytes() else "drift"


def skill_name_from_text(source: str) -> str | None:
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


def installed_skill_name(target: Path) -> str | None:
    try:
        source = (target / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return skill_name_from_text(source)


def skill_status(name: str, source: Path, target: Path) -> str:
    if not os.path.lexists(target):
        return "missing" if parent_directory_available(target) else "conflict"
    if target.is_symlink() and target.resolve() == source.resolve():
        return "current"
    if installed_skill_name(target) == name:
        return "external"
    return "conflict"


def hook_command(codex_home: Path, script: str) -> str:
    interpreter = str(Path(sys.executable).resolve()).replace('"', '\\"')
    hook_path = str(codex_home / "hooks" / script).replace('"', '\\"')
    return f'"{interpreter}" "{hook_path}"'


def reconcile_hooks(data: dict, codex_home: Path) -> dict:
    updated = copy.deepcopy(data)
    events = updated.setdefault("hooks", {})
    if not isinstance(events, dict):
        raise ValueError("hooks.json field 'hooks' must be an object")
    for event, script in HOOK_SPECS.items():
        managed_command = hook_command(codex_home, script)
        groups = events.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"hooks.json event '{event}' must be a list")
        for group in groups:
            if not isinstance(group, dict):
                continue
            hooks = group.get("hooks", [])
            if isinstance(hooks, list):
                group["hooks"] = [
                    hook
                    for hook in hooks
                    if not (
                        isinstance(hook, dict)
                        and hook.get("type") == "command"
                        and hook.get("command") == managed_command
                    )
                ]
        groups[:] = [group for group in groups if not isinstance(group, dict) or group.get("hooks")]
        groups.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": managed_command,
                    }
                ]
            }
        )
    return updated


def plan_skills(codex_home: Path, replace: bool) -> tuple[list[tuple[str, Path, Path, str]], bool]:
    plans: list[tuple[str, Path, Path, str]] = []
    healthy = True
    for name, source in BUNDLED_SKILLS.items():
        target = codex_home / "skills" / name
        status = skill_status(name, source, target)
        if status == "current":
            action = "current"
        elif status == "external":
            action = "replace" if replace and target.is_symlink() else "reuse"
        elif status == "missing":
            action = "create"
        elif replace and target.is_symlink():
            action = "replace"
        else:
            action = "conflict"
            healthy = False
        plans.append((name, source, target, action))
    return plans, healthy


def execute_skill_plans(
    plans: list[tuple[str, Path, Path, str]], apply: bool, healthy: bool
) -> bool:
    changed = False
    for name, source, target, action in plans:
        if action == "current":
            print(f"CURRENT skill: {name}: {target}")
            continue
        if action == "reuse":
            print(f"REUSE existing skill: {name}: {target}")
            continue
        if action == "conflict":
            print(f"REFUSED skill conflict: {name}: {target}; move it manually")
            continue
        changed = True
        label = "CREATE" if action == "create" else "REPLACE"
        if not apply or not healthy:
            print(f"WOULD {label} skill link: {name}: {target} -> {source}")
            continue
        atomic_symlink(source, target)
        print(f"{label}D skill link: {name}: {target}")
    return changed


def plan_files(
    specs: list[tuple[Path, Path]], replace: bool
) -> tuple[list[tuple[Path, Path, str]], bool]:
    plans: list[tuple[Path, Path, str]] = []
    healthy = True
    for source, target in specs:
        status = file_status(source, target)
        if status in {"current", "missing"}:
            action = "current" if status == "current" else "create"
        elif status == "drift" and replace:
            action = "replace"
        elif status == "conflict" and replace and target.is_symlink():
            action = "replace"
        else:
            action = status
            healthy = False
        plans.append((source, target, action))
    return plans, healthy


def execute_file_plans(plans: list[tuple[Path, Path, str]], apply: bool, healthy: bool) -> bool:
    changed = False
    for source, target, action in plans:
        if action == "current":
            print(f"CURRENT: {target}")
            continue
        if action == "drift":
            print(f"REFUSED drift: {target}; review it and add --replace")
            changed = True
            continue
        if action == "conflict":
            print(f"REFUSED file conflict: {target}; move it manually")
            changed = True
            continue
        changed = True
        label = "CREATE" if action == "create" else "REPLACE"
        if not apply or not healthy:
            print(f"WOULD {label}: {target}")
            continue
        atomic_write(target, source.read_bytes())
        print(f"{label}D: {target}")
    return changed


def validate_routing_source(source: Path) -> None:
    text = source.read_text(encoding="utf-8")
    for placeholder in ("MODEL_ID_", "REASONING_LEVEL", "SERVICE_TIER"):
        if placeholder in text:
            raise ValueError(f"routing config still contains placeholder: {placeholder}")
    if "[[roles." not in text or "model =" not in text:
        raise ValueError("routing config has no role route entries")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--with-hooks", action="store_true")
    parser.add_argument("--routing-config", type=Path)
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("UNSUPPORTED: this release installs on macOS only")
        return 2
    if args.apply and args.check:
        parser.error("--apply and --check are mutually exclusive")

    codex_home = args.codex_home.expanduser().resolve()
    changed = False

    routing_source: Path | None = None
    if args.routing_config:
        candidate = args.routing_config.expanduser().resolve()
        try:
            validate_routing_source(candidate)
        except (OSError, ValueError) as error:
            print(f"INVALID routing config: {error}")
            return 1
        routing_source = candidate

    hooks_path: Path | None = None
    hooks_data: dict | None = None
    expected_hooks: dict | None = None
    if args.with_hooks:
        candidate_hooks_path = codex_home / "hooks.json"
        try:
            loaded = (
                json.loads(candidate_hooks_path.read_text(encoding="utf-8"))
                if candidate_hooks_path.exists()
                else {}
            )
            if not isinstance(loaded, dict):
                raise ValueError("hooks.json root must be an object")
            hooks_data = loaded
            expected_hooks = reconcile_hooks(hooks_data, codex_home)
        except (json.JSONDecodeError, OSError, ValueError) as error:
            print(f"INVALID hooks config: {candidate_hooks_path}: {error}")
            return 1
        hooks_path = candidate_hooks_path

    skill_plans, skills_healthy = plan_skills(codex_home, args.replace)
    file_specs = [
        (source, codex_home / "agents" / source.name)
        for source in sorted((ROOT / "agents").glob("*.toml"))
    ]
    if args.with_hooks:
        file_specs.extend(
            (source, codex_home / "hooks" / source.name)
            for source in sorted((ROOT / "hooks").glob("*.py"))
        )
    if routing_source:
        file_specs.append((routing_source, codex_home / SKILL_NAME / "model-routing.toml"))

    file_plans, files_healthy = plan_files(file_specs, args.replace)
    install_healthy = skills_healthy and files_healthy
    changed |= execute_skill_plans(skill_plans, args.apply, install_healthy)
    changed |= execute_file_plans(file_plans, args.apply, install_healthy)

    hooks_changed = bool(
        args.with_hooks and expected_hooks is not None and expected_hooks != hooks_data
    )
    changed |= hooks_changed
    if not install_healthy:
        return 1

    if args.with_hooks:
        assert hooks_path is not None
        assert hooks_data is not None
        assert expected_hooks is not None
        if not hooks_changed:
            print(f"CURRENT: {hooks_path}")
        elif not args.apply:
            print(f"WOULD UPDATE: {hooks_path}")
        else:
            atomic_write(
                hooks_path,
                (json.dumps(expected_hooks, indent=2, sort_keys=True) + "\n").encode(),
            )
            print(f"UPDATED: {hooks_path}")

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
