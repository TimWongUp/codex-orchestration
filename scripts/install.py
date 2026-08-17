#!/usr/bin/env python3
"""Install or inspect codex-orchestration in a macOS Codex home."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "codex-orchestration"
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


def file_status(source: Path, target: Path) -> str:
    if not target.is_file():
        return "missing"
    return "current" if source.read_bytes() == target.read_bytes() else "drift"


def skill_status(target: Path) -> str:
    if not os.path.lexists(target):
        return "missing"
    if target.is_symlink() and target.resolve() == ROOT:
        return "current"
    return "drift"


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
                    if not (isinstance(hook, dict) and script in str(hook.get("command", "")))
                ]
        groups[:] = [group for group in groups if not isinstance(group, dict) or group.get("hooks")]
        groups.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command(codex_home, script),
                    }
                ]
            }
        )
    return updated


def install_skill(target: Path, apply: bool, replace: bool) -> tuple[bool, bool]:
    current = skill_status(target)
    if current == "current":
        print(f"CURRENT skill: {target}")
        return True, False
    if current == "drift" and not replace:
        print(f"REFUSED skill drift: {target}; review it and add --replace")
        return False, True
    label = "WOULD CREATE" if current == "missing" else "WOULD REPLACE"
    if not apply:
        print(f"{label} skill link: {target} -> {ROOT}")
        return True, True
    if current == "drift":
        if not target.is_symlink():
            print(f"REFUSED non-symlink skill target: {target}; move it manually")
            return False, True
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(ROOT, target_is_directory=True)
    print(f"{'CREATED' if current == 'missing' else 'REPLACED'} skill link: {target}")
    return True, True


def install_file(source: Path, target: Path, apply: bool, replace: bool) -> tuple[bool, bool]:
    current = file_status(source, target)
    if current == "current":
        print(f"CURRENT: {target}")
        return True, False
    if current == "drift" and not replace:
        print(f"REFUSED drift: {target}; review it and add --replace")
        return False, True
    label = "WOULD CREATE" if current == "missing" else "WOULD REPLACE"
    if not apply:
        print(f"{label}: {target}")
        return True, True
    atomic_write(target, source.read_bytes())
    print(f"{'CREATED' if current == 'missing' else 'REPLACED'}: {target}")
    return True, True


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
    healthy = True
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

    ok, differs = install_skill(codex_home / "skills" / SKILL_NAME, args.apply, args.replace)
    healthy &= ok
    changed |= differs

    for source in sorted((ROOT / "agents").glob("*.toml")):
        ok, differs = install_file(
            source, codex_home / "agents" / source.name, args.apply, args.replace
        )
        healthy &= ok
        changed |= differs

    if args.with_hooks:
        hook_files_healthy = True
        for source in sorted((ROOT / "hooks").glob("*.py")):
            ok, differs = install_file(
                source, codex_home / "hooks" / source.name, args.apply, args.replace
            )
            healthy &= ok
            hook_files_healthy &= ok
            changed |= differs

        assert hooks_path is not None
        assert hooks_data is not None
        assert expected_hooks is not None
        hooks_current = expected_hooks == hooks_data
        changed |= not hooks_current
        if not hook_files_healthy:
            print(f"SKIPPED hooks registry: {hooks_path}; hook files are not ready")
        elif hooks_current:
            print(f"CURRENT: {hooks_path}")
        elif not args.apply:
            print(f"WOULD UPDATE: {hooks_path}")
        else:
            atomic_write(
                hooks_path,
                (json.dumps(expected_hooks, indent=2, sort_keys=True) + "\n").encode(),
            )
            print(f"UPDATED: {hooks_path}")

    if routing_source:
        ok, differs = install_file(
            routing_source,
            codex_home / SKILL_NAME / "model-routing.toml",
            args.apply,
            args.replace,
        )
        healthy &= ok
        changed |= differs

    if not healthy:
        return 1
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
