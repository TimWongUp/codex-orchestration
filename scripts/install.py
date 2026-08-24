#!/usr/bin/env python3
"""Plan or apply a Codex Orchestration runtime projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

import validate as contract

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_RULES_CANDIDATES = ("AGENTS.md", "AGENTS.override.md")
WINDOWS_CONSERVATIVE_PATH_LIMIT = 248
TEMPORARY_TOKEN_LENGTH = 24


@dataclass(frozen=True)
class Operation:
    kind: str
    path: Path
    reason: str
    content: bytes | None = None
    expected: bytes | None = None
    preconditions: tuple[tuple[Path, bytes | None], ...] = ()


@dataclass
class InstallPlan:
    codex_home: Path
    skills_root: Path
    operations: list[Operation] = field(default_factory=list)
    current: list[tuple[Path, str]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    global_rules_target: Path | None = None
    hook_registration: dict[str, object] | None = None

    def add_write(
        self,
        path: Path,
        content: bytes,
        reason: str,
        *,
        expected: bytes | None = None,
        use_expected: bool = False,
        preconditions: tuple[tuple[Path, bytes | None], ...] = (),
    ) -> None:
        planned = expected
        if not use_expected and path.is_file() and not contract.path_is_link_like(path):
            try:
                planned = path.read_bytes()
            except OSError as error:
                self.conflicts.append(f"unreadable target: {path}: {error}")
                return
        if planned == content:
            self.current.append((path, reason))
            return
        self.operations.append(Operation("write", path, reason, content, planned, preconditions))

    def add_delete(
        self,
        path: Path,
        reason: str,
        *,
        expected: bytes | None = None,
        use_expected: bool = False,
    ) -> None:
        if not use_expected:
            try:
                expected = path.read_bytes()
            except OSError as error:
                self.conflicts.append(f"unreadable removal target: {path}: {error}")
                return
        if expected is None:
            self.conflicts.append(f"removal target disappeared while planning: {path}")
            return
        self.operations.append(Operation("delete", path, reason, expected=expected))


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def ensure_physical_root(path: Path, label: str, plan: InstallPlan) -> bool:
    linked = contract.first_symlink_component(path)
    if linked is not None:
        plan.conflicts.append(f"{label} has linked path component: {linked}")
        return False
    if lexists(path):
        if not path.is_dir():
            plan.conflicts.append(f"{label} conflicting: {path}")
            return False
        return True
    ancestor = path.parent
    while not lexists(ancestor) and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if contract.path_is_link_like(ancestor) or not ancestor.is_dir():
        plan.conflicts.append(f"{label} nearest existing ancestor is not physical: {ancestor}")
        return False
    return True


def ensure_physical_parents(path: Path, root: Path, label: str, plan: InstallPlan) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        plan.conflicts.append(f"{label} escapes selected root: {path}")
        return False
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if not lexists(current):
            continue
        if contract.path_is_link_like(current) or not current.is_dir():
            plan.conflicts.append(f"{label} parent linked or conflicting: {current}")
            return False
    return True


def regular_target(path: Path, root: Path, label: str, plan: InstallPlan) -> bool:
    if os.name == "nt" and any(
        len(str(candidate.absolute())) >= WINDOWS_CONSERVATIVE_PATH_LIMIT
        for candidate in (
            path,
            installer_temporary_path(path, "0" * TEMPORARY_TOKEN_LENGTH),
        )
    ):
        plan.conflicts.append(f"{label} exceeds conservative Windows path limit: {path}")
        return False
    if not ensure_physical_parents(path, root, label, plan):
        return False
    if lexists(path) and (contract.path_is_link_like(path) or not path.is_file()):
        plan.conflicts.append(f"{label} linked or conflicting: {path}")
        return False
    return True


def source_skill_files(name: str, source_root: Path) -> list[Path]:
    if name == "codex-orchestration":
        files = [source_root / "SKILL.md"]
        files.extend(path for path in (source_root / "references").rglob("*") if path.is_file())
        return sorted(files)
    return sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def read_managed_source(path: Path, label: str, plan: InstallPlan) -> bytes | None:
    try:
        path.relative_to(ROOT)
    except ValueError:
        plan.conflicts.append(f"{label} escapes source checkout: {path}")
        return None
    if contract.has_symlink_component(path, ROOT):
        plan.conflicts.append(f"{label} has linked source path: {path}")
        return None
    try:
        return path.read_bytes()
    except OSError as error:
        plan.conflicts.append(f"{label} unreadable: {path}: {error}")
        return None


def plan_skill(
    plan: InstallPlan,
    name: str,
    source_root: Path,
    target_root: Path,
) -> None:
    if lexists(target_root) and (
        contract.path_is_link_like(target_root) or not target_root.is_dir()
    ):
        plan.conflicts.append(f"Skill target linked or conflicting: {target_root}")
        return
    target_entry = target_root / "SKILL.md"
    if (
        target_root.is_dir()
        and target_entry.is_file()
        and not contract.path_is_link_like(target_entry)
    ):
        try:
            target_name = contract.skill_document_name(target_entry.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            plan.conflicts.append(f"Skill entry unreadable: {target_entry}: {error}")
            return
        if target_name != name:
            plan.conflicts.append(
                f"Skill target belongs to {target_name or 'an unknown Skill'}: {target_root}"
            )
            return
    elif target_root.is_dir() and any(target_root.iterdir()):
        plan.conflicts.append(f"non-empty Skill target has no physical SKILL.md: {target_root}")
        return

    for source in source_skill_files(name, source_root):
        target = target_root / source.relative_to(source_root)
        content = read_managed_source(source, "managed Skill source", plan)
        if content is not None and regular_target(target, plan.skills_root, "Skill file", plan):
            plan.add_write(target, content, f"managed Skill {name}")


def plan_agents(plan: InstallPlan) -> None:
    agents_root = plan.codex_home / "agents"
    if lexists(agents_root) and (
        contract.path_is_link_like(agents_root) or not agents_root.is_dir()
    ):
        plan.conflicts.append(f"Agent directory linked or conflicting: {agents_root}")
        return
    for source in sorted((ROOT / "agents").glob("*.toml")):
        target = agents_root / source.name
        content = read_managed_source(source, "managed Agent source", plan)
        if content is not None and regular_target(target, plan.codex_home, "Agent file", plan):
            plan.add_write(target, content, "managed Agent profile")


def plan_preferences(plan: InstallPlan, language: str | None) -> None:
    target = plan.codex_home / "codex-orchestration" / "preferences.toml"
    if not regular_target(target, plan.codex_home, "task-package preference", plan):
        return
    existing_language: str | None = None
    existing_content: bytes | None = None
    if target.is_file():
        try:
            existing_content = target.read_bytes()
            source = existing_content.decode("utf-8")
        except (OSError, UnicodeError) as error:
            plan.conflicts.append(f"task-package preference unreadable: {target}: {error}")
            return
        failures = contract.preferences_failures(source)
        if failures:
            plan.conflicts.append(f"task-package preference invalid: {target}: {failures[0]}")
            return
        existing_language = contract.top_level_values(source).get("task_package_language")
    if language is None:
        if existing_language is None:
            plan.conflicts.append("first install requires --language en or --language zh-CN")
        else:
            plan.current.append((target, f"task-package language {existing_language}"))
        return
    template = read_managed_source(
        ROOT / "examples" / "preferences.toml", "task-package preference source", plan
    )
    if template is None:
        return
    rendered = template.replace(b"LANGUAGE", language.encode("utf-8"))
    plan.add_write(
        target,
        rendered,
        f"task-package language {language}",
        expected=existing_content,
        use_expected=True,
    )


def newline_for(content: bytes) -> bytes:
    without_crlf = content.replace(b"\r\n", b"")
    return b"\r\n" if b"\r\n" in content and b"\n" not in without_crlf else b"\n"


def render_block_for(content: bytes, canonical: bytes) -> bytes:
    newline = newline_for(content)
    normalized = canonical.replace(b"\r\n", b"\n")
    return normalized.replace(b"\n", newline)


def append_managed_block(content: bytes, block: bytes) -> bytes:
    if not content:
        return block
    newline = newline_for(content)
    separator = b""
    if not content.endswith((b"\n", b"\r")):
        separator += newline
    if not (content + separator).endswith(newline + newline):
        separator += newline
    return content + separator + block


def plan_global_rules(plan: InstallPlan) -> None:
    target, target_error = contract.active_global_rules_target(plan.codex_home)
    if target_error is not None or target is None:
        plan.conflicts.append(target_error or "global instructions target could not be resolved")
        return
    plan.global_rules_target = target
    canonical = read_managed_source(contract.GLOBAL_RULES_TEMPLATE, "global rules template", plan)
    if canonical is None:
        return

    for filename in GLOBAL_RULES_CANDIDATES:
        candidate = plan.codex_home / filename
        if not regular_target(candidate, plan.codex_home, "global instructions", plan):
            continue
        try:
            exists = candidate.is_file()
            content = candidate.read_bytes() if exists else b""
        except OSError as error:
            plan.conflicts.append(f"global instructions unreadable: {candidate}: {error}")
            continue
        state, ranges = contract.managed_global_rules_ranges(content)
        if state == "corrupt" or len(ranges) > 1:
            plan.conflicts.append(f"global rules markers corrupt or duplicated: {candidate}")
            continue
        if candidate != target:
            if ranges:
                start, end = ranges[0]
                plan.add_write(
                    candidate,
                    content[:start] + content[end:],
                    "remove inactive managed global-rules block",
                    expected=content,
                    use_expected=True,
                )
            continue

        block = render_block_for(content, canonical)
        if ranges:
            start, end = ranges[0]
            rendered = content[:start] + block + content[end:]
        else:
            rendered = append_managed_block(content, block)
        plan.add_write(
            candidate,
            rendered,
            "active managed global-rules block",
            expected=content if exists else None,
            use_expected=True,
        )


def script_basename(path: str, *, windows: bool) -> str:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.casefold() if windows or sys.platform == "darwin" else name


def handler_command_paths(handler: dict[str, object]) -> list[tuple[str | None, bool]]:
    fields: list[tuple[object, bool]] = []
    if handler.get("command") is not None:
        fields.append((handler.get("command"), os.name == "nt"))
    if handler.get("commandWindows") is not None:
        fields.append((handler.get("commandWindows"), True))
    return [
        (contract.python_hook_script(command, windows=windows), windows)
        for command, windows in fields
    ]


def handler_noncanonical_python_paths(handler: dict[str, object]) -> list[tuple[str, bool]]:
    fields: list[tuple[object, bool]] = []
    if handler.get("command") is not None:
        fields.append((handler.get("command"), os.name == "nt"))
    if handler.get("commandWindows") is not None:
        fields.append((handler.get("commandWindows"), True))
    paths: list[tuple[str, bool]] = []
    for command, windows in fields:
        if contract.python_hook_script(command, windows=windows) is not None:
            continue
        paths.extend(
            (path, windows) for path in contract.command_path_candidates(command, windows=windows)
        )
    return paths


def same_hook_path(left: str | Path, right: str | Path, *, windows: bool) -> bool:
    return contract.hook_paths_may_alias(left, right, windows=windows)


def authenticated_retired_path(
    path_value: str, expected_path: Path, filename: str, *, windows: bool
) -> bool:
    if script_basename(path_value, windows=windows) != script_basename(filename, windows=windows):
        return False
    if not same_hook_path(path_value, expected_path, windows=windows):
        return False
    path = Path(path_value)
    if contract.first_symlink_component(path) is not None or not path.is_file():
        return False
    try:
        digest = contract.file_sha256(path)
    except OSError:
        return False
    if filename == "orchestration_route.py":
        return digest in contract.RETIRED_ROUTE_SHA256
    return digest in contract.RETIRED_HOOK_SHA256.get(filename, frozenset())


def remove_owned_hook_handlers(
    data: dict[str, object],
    managed_target: Path,
    plan: InstallPlan,
    *,
    replace_current: bool,
) -> tuple[dict[str, object], bool]:
    if "hooks" not in data:
        hooks_value: object = {}
    else:
        hooks_value = data["hooks"]
    if not isinstance(hooks_value, dict):
        plan.conflicts.append("hooks.json must contain an object-valued hooks field")
        return data, False
    changed = False
    rebuilt_events: dict[str, object] = {}

    for event, groups_value in hooks_value.items():
        if not isinstance(groups_value, list):
            plan.conflicts.append(f"hooks.json event must be a list: {event}")
            rebuilt_events[event] = groups_value
            continue
        rebuilt_groups: list[object] = []
        for group_value in groups_value:
            if not isinstance(group_value, dict) or not isinstance(group_value.get("hooks"), list):
                rebuilt_groups.append(group_value)
                continue
            matcher = group_value.get("matcher")
            rebuilt_handlers: list[object] = []
            for handler_value in group_value["hooks"]:
                if not isinstance(handler_value, dict) or handler_value.get("type") != "command":
                    rebuilt_handlers.append(handler_value)
                    continue
                noncanonical_conflict = False
                for path, windows in handler_noncanonical_python_paths(handler_value):
                    basename = script_basename(path, windows=windows)
                    managed_name = script_basename("subagent_scope.py", windows=windows)
                    route_name = script_basename("orchestration_route.py", windows=windows)
                    guard_name = script_basename("subagent_guard.py", windows=windows)
                    noncanonical_conflict = noncanonical_conflict or (
                        (
                            basename in {managed_name, route_name, guard_name}
                            and contract.hook_path_is_ambiguous(path, windows=windows)
                        )
                        or same_hook_path(path, managed_target, windows=windows)
                        or same_hook_path(
                            path,
                            plan.codex_home / "hooks" / "orchestration_route.py",
                            windows=windows,
                        )
                        or same_hook_path(
                            path,
                            plan.codex_home / "hooks" / "subagent_guard.py",
                            windows=windows,
                        )
                        or contract.referenced_script_has_retired_hash(path, windows=windows)
                    )
                if noncanonical_conflict:
                    plan.conflicts.append(
                        f"managed-looking Hook registration is not a canonical command: {event}"
                    )
                    rebuilt_handlers.append(handler_value)
                    continue
                fields = handler_command_paths(handler_value)
                unsafe_project_fields: list[bool] = []
                current_fields = [
                    path is not None and same_hook_path(path, managed_target, windows=windows)
                    for path, windows in fields
                ]
                owned_current = bool(current_fields) and all(current_fields)
                mixed_current = any(current_fields) and not owned_current
                retired_fields: list[bool] = []
                retired_relevant: list[bool] = []
                for path, windows in fields:
                    if path is None:
                        retired_fields.append(False)
                        retired_relevant.append(False)
                        continue
                    basename = script_basename(path, windows=windows)
                    managed_name = script_basename("subagent_scope.py", windows=windows)
                    route_name = script_basename("orchestration_route.py", windows=windows)
                    guard_name = script_basename("subagent_guard.py", windows=windows)
                    route_path = plan.codex_home / "hooks" / "orchestration_route.py"
                    guard_path = plan.codex_home / "hooks" / "subagent_guard.py"
                    aliases_route = same_hook_path(path, route_path, windows=windows)
                    aliases_guard = same_hook_path(path, guard_path, windows=windows)
                    references_retired_code = contract.referenced_script_has_retired_hash(
                        path, windows=windows
                    )
                    unsafe_project_fields.append(
                        basename in {managed_name, route_name, guard_name}
                        and contract.hook_path_is_ambiguous(path, windows=windows)
                    )
                    is_route_shape = event == "UserPromptSubmit" and basename == route_name
                    is_guard_shape = (
                        isinstance(matcher, str)
                        and (event, matcher) in contract.LEGACY_HOOK_GROUPS
                        and basename == guard_name
                    )
                    filename = (
                        "orchestration_route.py"
                        if basename == route_name or aliases_route
                        else "subagent_guard.py"
                    )
                    expected_path = plan.codex_home / "hooks" / filename
                    points_to_retired_target = aliases_route or aliases_guard
                    retired_shape = is_route_shape or is_guard_shape
                    retired_relevant.append(
                        retired_shape or points_to_retired_target or references_retired_code
                    )
                    retired_fields.append(
                        retired_shape
                        and authenticated_retired_path(
                            path,
                            expected_path,
                            filename,
                            windows=windows,
                        )
                    )
                retired = bool(retired_fields) and all(retired_fields)
                suspicious_retired = any(retired_relevant) and not retired
                if any(unsafe_project_fields):
                    plan.conflicts.append(
                        f"managed-looking Hook registration has unsafe path: {event}"
                    )
                    rebuilt_handlers.append(handler_value)
                elif mixed_current:
                    plan.conflicts.append(
                        f"managed-looking Hook registration has mixed ownership: {event}"
                    )
                    rebuilt_handlers.append(handler_value)
                elif suspicious_retired:
                    plan.conflicts.append(
                        f"retired-looking Hook registration has unconfirmed ownership: {event}"
                    )
                    rebuilt_handlers.append(handler_value)
                elif (replace_current and owned_current) or retired:
                    changed = True
                else:
                    rebuilt_handlers.append(handler_value)
            if rebuilt_handlers:
                rebuilt_group = dict(group_value)
                rebuilt_group["hooks"] = rebuilt_handlers
                rebuilt_groups.append(rebuilt_group)
            elif group_value["hooks"]:
                changed = True
            else:
                rebuilt_groups.append(group_value)
        rebuilt_events[event] = rebuilt_groups
    rebuilt = dict(data)
    rebuilt["hooks"] = rebuilt_events
    return rebuilt, changed


def desired_hook_registration(target: Path) -> dict[str, object]:
    use_windows = os.name == "nt"
    command = contract.expected_hook_command(target, windows=use_windows)
    handler: dict[str, object] = {
        "type": "command",
        "command": command,
        "timeout": 5,
        "statusMessage": "Checking worker write lease",
    }
    if use_windows:
        handler["commandWindows"] = command
    return {"hooks": [handler]}


def plan_retired_hook_files(plan: InstallPlan) -> None:
    hooks_root = plan.codex_home / "hooks"
    if not lexists(hooks_root):
        return
    if contract.path_is_link_like(hooks_root) or not hooks_root.is_dir():
        plan.conflicts.append(f"Hook directory linked or conflicting: {hooks_root}")
        return
    candidates = [*contract.RETIRED_HOOK_SCRIPTS, "orchestration_route.py"]
    for filename in candidates:
        target = hooks_root / filename
        if not lexists(target):
            continue
        if not regular_target(target, plan.codex_home, "retired Hook path", plan):
            continue
        try:
            retired_content = target.read_bytes()
        except OSError as error:
            plan.conflicts.append(f"retired Hook path unreadable: {target}: {error}")
            continue
        digest = sha256_bytes(retired_content)
        known = (
            digest in contract.RETIRED_ROUTE_SHA256
            if filename == "orchestration_route.py"
            else digest in contract.RETIRED_HOOK_SHA256[filename]
        )
        if known:
            plan.add_delete(
                target,
                "confirmed retired project Hook",
                expected=retired_content,
                use_expected=True,
            )
        else:
            plan.conflicts.append(f"retired Hook path ownership conflict: {target}")


def plan_hooks(plan: InstallPlan, install_hook: bool) -> None:
    plan_retired_hook_files(plan)
    hooks_path = plan.codex_home / "hooks.json"
    managed_target = plan.codex_home / "hooks" / "subagent_scope.py"
    if not regular_target(hooks_path, plan.codex_home, "hooks config", plan):
        return
    if hooks_path.is_file():
        try:
            hooks_content = hooks_path.read_bytes()
            data = contract.strict_json_loads(hooks_content)
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
            plan.conflicts.append(f"hooks config invalid: {hooks_path}: {error}")
            return
        if not isinstance(data, dict):
            plan.conflicts.append(f"hooks config root must be an object: {hooks_path}")
            return
    else:
        hooks_content = None
        data = {"description": "Codex Orchestration lifecycle hooks.", "hooks": {}}

    reconciled, changed = remove_owned_hook_handlers(
        data, managed_target, plan, replace_current=install_hook
    )
    hooks_value = reconciled.get("hooks")
    if not isinstance(hooks_value, dict):
        return
    if install_hook:
        if os.name == "nt" and (
            contract.unsafe_windows_hook_path(Path(sys.executable).absolute())
            or contract.unsafe_windows_hook_path(managed_target.absolute())
        ):
            plan.conflicts.append(
                f"Hook command path contains unsafe Windows expansion characters: {managed_target}"
            )
            return
        if not regular_target(managed_target, plan.codex_home, "Hook script", plan):
            return
        hook_source = read_managed_source(
            ROOT / "hooks" / "subagent_scope.py", "writer-lease Hook source", plan
        )
        if hook_source is None:
            return
        plan.add_write(managed_target, hook_source, "writer-lease Hook")
        registration = desired_hook_registration(managed_target)
        plan.hook_registration = registration
        current_groups = hooks_value.get("SubagentStart")
        if current_groups is None:
            current_groups = []
        if not isinstance(current_groups, list):
            plan.conflicts.append("hooks.json SubagentStart event must be a list")
            return
        hooks_value["SubagentStart"] = [*current_groups, registration]
        changed = True
    if changed:
        rendered = (json.dumps(reconciled, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        plan.add_write(
            hooks_path,
            rendered,
            "owned Hook registration reconciliation",
            expected=hooks_content,
            use_expected=True,
            preconditions=tuple(
                (operation.path, None)
                for operation in plan.operations
                if operation.kind == "delete"
            ),
        )


def build_plan(
    codex_home: Path,
    skills_root: Path,
    *,
    language: str | None,
    install_hook: bool,
    global_rules: bool,
) -> InstallPlan:
    raw_codex_home = codex_home.absolute()
    raw_skills_root = skills_root.absolute()
    codex_home = contract.canonical_selected_root(raw_codex_home)
    skills_root = contract.canonical_selected_root(raw_skills_root)
    plan = InstallPlan(codex_home=codex_home, skills_root=skills_root)
    for label, raw_root in (
        ("Codex home", raw_codex_home),
        ("Skill root", raw_skills_root),
    ):
        if contract.path_is_link_like(raw_root):
            plan.conflicts.append(f"{label} linked or conflicting: {raw_root}")
            continue
        linked = contract.first_symlink_component(raw_root)
        if linked is not None:
            plan.conflicts.append(f"{label} has linked or unsafe path component: {linked}")
    if plan.conflicts:
        return plan
    home_ok = ensure_physical_root(codex_home, "Codex home", plan)
    skills_ok = ensure_physical_root(skills_root, "Skill root", plan)
    if not home_ok or not skills_ok:
        return plan

    for name, source_root in contract.BUNDLED_SKILLS.items():
        plan_skill(plan, name, source_root, skills_root / name)
    plan_agents(plan)
    plan_preferences(plan, language)
    if global_rules:
        plan_global_rules(plan)
    plan_hooks(plan, install_hook)
    return plan


def replace_temporary_file(temporary: Path, path: Path) -> None:
    if os.name != "nt" or not path.is_file():
        os.replace(temporary, path)
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    replace_file = kernel32.ReplaceFileW
    replace_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    )
    replace_file.restype = wintypes.BOOL
    if not replace_file(
        windows_extended_path(path.absolute()),
        windows_extended_path(temporary.absolute()),
        None,
        0,
        None,
        None,
    ):
        error = ctypes.get_last_error()  # type: ignore[attr-defined]
        raise OSError(error, ctypes.FormatError(error), str(path))  # type: ignore[attr-defined]


def windows_extended_path(path: str | Path) -> str:
    value = str(path)
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def installer_temporary_path(path: Path, token: str) -> Path:
    return path.with_name(f".{path.name}.codex-orchestration-{token}")


def atomic_write(path: Path, content: bytes) -> None:
    temporary = installer_temporary_path(path, secrets.token_hex(12))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if os.name != "nt" and path.is_file():
                mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
                os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        replace_temporary_file(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def create_parent_directories(path: Path, created: list[Path]) -> None:
    missing: list[Path] = []
    current = path.parent
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        created.append(directory)


def rollback(
    plan: InstallPlan,
    completed: list[Operation],
    previous: dict[Path, bytes | None],
    created_directories: list[Path],
) -> list[str]:
    failures: list[str] = []
    for operation in reversed(completed):
        old_content = previous[operation.path]
        try:
            root = operation_root(plan, operation.path)
            probe = InstallPlan(codex_home=plan.codex_home, skills_root=plan.skills_root)
            if not ensure_physical_root(root, "rollback root", probe) or not regular_target(
                operation.path, root, "rollback target", probe
            ):
                failures.append(
                    f"rollback refused conflicting target: {operation.path}: {probe.conflicts[0]}"
                )
                continue
            current = operation.path.read_bytes() if operation.path.is_file() else None
            installed = operation.content if operation.kind == "write" else None
            if current == old_content:
                continue
            if current != installed:
                failures.append(f"rollback refused changed target: {operation.path}")
                continue
            if old_content is None:
                if lexists(operation.path):
                    operation.path.unlink()
            else:
                atomic_write(operation.path, old_content)
        except OSError as error:
            failures.append(f"rollback failed: {operation.path}: {error}")
    for directory in reversed(created_directories):
        try:
            directory.rmdir()
        except OSError:
            pass
    return failures


def verification_failures(
    plan: InstallPlan, *, install_hook: bool, global_rules: bool
) -> list[str]:
    failures = contract.validate_source()
    failures.extend(contract.validate_runtime(plan.codex_home, plan.skills_root))
    if install_hook:
        failures.extend(contract.validate_hooks(plan.codex_home))
    if global_rules:
        failures.extend(contract.validate_global_rules(plan.codex_home))
    return failures


def operation_root(plan: InstallPlan, path: Path) -> Path:
    candidates = [root for root in (plan.codex_home, plan.skills_root) if path.is_relative_to(root)]
    if not candidates:
        raise RuntimeError(f"transaction target escapes selected roots: {path}")
    return max(candidates, key=lambda candidate: len(candidate.parts))


def recheck_snapshot(plan: InstallPlan, path: Path, expected: bytes | None, label: str) -> None:
    root = operation_root(plan, path)
    probe = InstallPlan(codex_home=plan.codex_home, skills_root=plan.skills_root)
    if not ensure_physical_root(root, "transaction root", probe):
        raise RuntimeError(probe.conflicts[0])
    if not regular_target(path, root, label, probe):
        raise RuntimeError(probe.conflicts[0])
    if expected is None:
        if lexists(path):
            raise RuntimeError(f"{label} appeared after planning: {path}")
        return
    if not path.is_file():
        raise RuntimeError(f"{label} disappeared after planning: {path}")
    try:
        current = path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"{label} unreadable: {path}: {error}") from error
    if current != expected:
        raise RuntimeError(f"{label} changed after planning: {path}")


def recheck_operation(plan: InstallPlan, operation: Operation) -> None:
    for path, expected in operation.preconditions:
        recheck_snapshot(plan, path, expected, "transaction precondition")
    recheck_snapshot(plan, operation.path, operation.expected, "transaction target")


def apply_plan(plan: InstallPlan, *, install_hook: bool, global_rules: bool) -> None:
    if plan.conflicts:
        raise RuntimeError("installation plan has conflicts")
    previous: dict[Path, bytes | None] = {}
    completed: list[Operation] = []
    created_directories: list[Path] = []
    try:
        for operation in plan.operations:
            recheck_operation(plan, operation)
            previous[operation.path] = operation.expected
            create_parent_directories(operation.path, created_directories)
            completed.append(operation)
            if operation.kind == "write":
                if operation.content is None:
                    raise RuntimeError(f"write operation has no content: {operation.path}")
                atomic_write(operation.path, operation.content)
                recheck_snapshot(plan, operation.path, operation.content, "post-write target")
            else:
                operation.path.unlink()
                recheck_snapshot(plan, operation.path, None, "post-delete target")
        failures = verification_failures(plan, install_hook=install_hook, global_rules=global_rules)
        if failures:
            details = "\n".join(f"- {item}" for item in failures)
            raise RuntimeError(f"verification failed:\n{details}")
    except BaseException as error:
        rollback_failures = rollback(plan, completed, previous, created_directories)
        if rollback_failures:
            raise RuntimeError(f"{error}\n" + "\n".join(rollback_failures)) from error
        raise


def print_plan(plan: InstallPlan, *, install_hook: bool, global_rules: bool) -> None:
    print("Codex Orchestration installation plan")
    print(f"Codex home: {plan.codex_home}")
    print(f"Skill root: {plan.skills_root}")
    print(f"Global rules: {'managed block' if global_rules else 'unchanged'}")
    print(f"Writer-lease Hook: {'install/update' if install_hook else 'unchanged'}")
    for operation in plan.operations:
        label = (
            "REMOVE"
            if operation.kind == "delete"
            else ("UPDATE" if operation.path.is_file() else "CREATE")
        )
        digest = "" if operation.content is None else f" sha256={sha256_bytes(operation.content)}"
        print(f"[{label}] {operation.path} — {operation.reason}{digest}")
    if not plan.operations:
        print("[CURRENT] no managed runtime changes")
    if global_rules and plan.global_rules_target is not None:
        print(f"Active global instructions: {plan.global_rules_target}")
        print(contract.GLOBAL_RULES_TEMPLATE.read_text(encoding="utf-8").rstrip())
    if install_hook and plan.hook_registration is not None:
        print("Managed SubagentStart group:")
        print(json.dumps(plan.hook_registration, ensure_ascii=False, indent=2))
    for conflict in plan.conflicts:
        print(f"[CONFLICT] {conflict}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--language", choices=sorted(contract.TASK_PACKAGE_LANGUAGES))
    parser.add_argument("--hooks", action="store_true", help="install the writer-lease Hook")
    parser.add_argument(
        "--global-rules",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="inject the managed global AGENTS block (default: enabled)",
    )
    parser.add_argument("--apply", action="store_true", help="apply the displayed plan")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_failures = contract.validate_source()
    if source_failures:
        for failure in source_failures:
            print(f"FAIL: {failure}")
        return 1
    codex_home = args.codex_home.expanduser().absolute()
    skills_root = args.skills_root.expanduser().absolute()
    plan = build_plan(
        codex_home,
        skills_root,
        language=args.language,
        install_hook=args.hooks,
        global_rules=args.global_rules,
    )
    print_plan(plan, install_hook=args.hooks, global_rules=args.global_rules)
    if plan.conflicts:
        print("Refusing installation because the plan contains conflicts.")
        return 2
    if not args.apply:
        print("Dry run only. Re-run the same command with --apply to write these changes.")
        return 0
    try:
        apply_plan(plan, install_hook=args.hooks, global_rules=args.global_rules)
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}")
        return 1
    print("OK: installation applied and runtime verification passed")
    print("Start a new Codex task so Skills, Agents, global rules, and Hooks reload.")
    if args.hooks:
        print("Review and trust the installed Hook with /hooks before expecting it to run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
