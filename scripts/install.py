#!/usr/bin/env python3
"""Plan, apply, or uninstall a Codex Orchestration runtime projection."""

from __future__ import annotations

import argparse
import hashlib
import locale
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
    path: Path
    reason: str
    content: bytes | None
    expected: bytes | None = None


@dataclass
class InstallPlan:
    codex_home: Path
    skills_root: Path
    operations: list[Operation] = field(default_factory=list)
    current: list[tuple[Path, str]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    global_rules_target: Path | None = None
    model_routing_path: Path | None = None
    model_routing_state: str = "unchecked"

    def add_write(
        self,
        path: Path,
        content: bytes,
        reason: str,
        *,
        expected: bytes | None = None,
        use_expected: bool = False,
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
        self.operations.append(Operation(path, reason, content, planned))

    def add_delete(self, path: Path, content: bytes, reason: str) -> None:
        self.operations.append(Operation(path, reason, None, content))


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def same_physical_path(left: Path, right: Path) -> bool:
    try:
        return lexists(left) and lexists(right) and os.path.samefile(left, right)
    except OSError:
        return False


def paths_overlap(left: Path, right: Path) -> bool:
    if left.is_relative_to(right) or right.is_relative_to(left):
        return True
    if same_physical_path(left, right):
        return True
    if any(same_physical_path(candidate, right) for candidate in left.parents):
        return True
    return any(same_physical_path(candidate, left) for candidate in right.parents)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def detected_task_package_language() -> str:
    locale_name = next(
        (value for name in ("LC_ALL", "LC_MESSAGES", "LANG") if (value := os.environ.get(name))),
        None,
    )
    if locale_name is None:
        locale_name = locale.getlocale()[0] or ""
    normalized = locale_name.lower().replace("_", "-")
    is_chinese = (
        normalized == "zh" or normalized.startswith("zh-") or normalized.startswith("chinese")
    )
    return "zh-CN" if is_chinese else "en"


def prompt_task_package_language(default: str) -> str | None:
    while True:
        try:
            answer = input(f"Task package language [en/zh-CN] (default: {default}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not answer:
            return default
        normalized = answer.lower().replace("_", "-")
        if normalized == "en":
            return "en"
        if normalized == "zh-cn":
            return "zh-CN"
        print("Choose en or zh-CN.")


def confirm_apply(action: str = "installation") -> bool:
    try:
        answer = input(f"Apply this {action} plan? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes"}


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


def plan_owned_file_removal(
    plan: InstallPlan,
    path: Path,
    owned_content: bytes,
    reason: str,
    *,
    root: Path,
    label: str,
) -> None:
    if not regular_target(path, root, label, plan):
        return
    if not path.is_file():
        plan.current.append((path, f"{reason} already absent"))
        return
    try:
        current = path.read_bytes()
    except OSError as error:
        plan.conflicts.append(f"{label} unreadable: {path}: {error}")
        return
    if current != owned_content:
        plan.conflicts.append(f"{label} changed; refusing removal: {path}")
        return
    plan.add_delete(path, current, reason)


def plan_skill_removal(
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
    for source in source_skill_files(name, source_root):
        content = read_managed_source(source, "managed Skill source", plan)
        if content is None:
            continue
        target = target_root / source.relative_to(source_root)
        plan_owned_file_removal(
            plan,
            target,
            content,
            f"remove managed Skill {name}",
            root=plan.skills_root,
            label="managed Skill file",
        )


def plan_agent_removal(plan: InstallPlan) -> None:
    agents_root = plan.codex_home / "agents"
    if lexists(agents_root) and (
        contract.path_is_link_like(agents_root) or not agents_root.is_dir()
    ):
        plan.conflicts.append(f"Agent directory linked or conflicting: {agents_root}")
        return
    for source in sorted((ROOT / "agents").glob("*.toml")):
        content = read_managed_source(source, "managed Agent source", plan)
        if content is None:
            continue
        plan_owned_file_removal(
            plan,
            agents_root / source.name,
            content,
            "remove managed Agent profile",
            root=plan.codex_home,
            label="managed Agent file",
        )


def plan_preferences_removal(plan: InstallPlan) -> None:
    target = plan.codex_home / "codex-orchestration" / "preferences.toml"
    template = read_managed_source(
        ROOT / "examples" / "preferences.toml", "task-package preference source", plan
    )
    if template is None or not regular_target(
        target, plan.codex_home, "task-package preference", plan
    ):
        return
    if not target.is_file():
        plan.current.append((target, "task-package preference already absent"))
        return
    try:
        current = target.read_bytes()
    except OSError as error:
        plan.conflicts.append(f"task-package preference unreadable: {target}: {error}")
        return
    rendered = {
        template.replace(b"LANGUAGE", language.encode("utf-8"))
        for language in contract.TASK_PACKAGE_LANGUAGES
    }
    if current not in rendered:
        plan.conflicts.append(f"task-package preference changed; refusing removal: {target}")
        return
    plan.add_delete(target, current, "remove managed task-package preference")


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


def check_unchanged_global_rules(plan: InstallPlan) -> None:
    """Reject stale owned policy while honoring an explicit no-injection choice."""
    canonical = read_managed_source(contract.GLOBAL_RULES_TEMPLATE, "global rules template", plan)
    if canonical is None:
        return
    for filename in GLOBAL_RULES_CANDIDATES:
        candidate = plan.codex_home / filename
        if not regular_target(candidate, plan.codex_home, "global instructions", plan):
            continue
        try:
            if not candidate.is_file():
                continue
            content = candidate.read_bytes()
        except OSError as error:
            plan.conflicts.append(f"global instructions unreadable: {candidate}: {error}")
            continue
        state, ranges = contract.managed_global_rules_ranges(content)
        if state == "corrupt" or len(ranges) > 1:
            plan.conflicts.append(f"global rules markers corrupt or duplicated: {candidate}")
            continue
        if not ranges:
            continue
        start, end = ranges[0]
        if content[start:end] != render_block_for(content, canonical):
            plan.conflicts.append(
                "managed global-rules block is stale; rerun without --no-global-rules to "
                f"migrate it: {candidate}"
            )
            continue
        plan.current.append((candidate, "current managed global-rules block left unchanged"))


def plan_global_rules_removal(plan: InstallPlan) -> None:
    for filename in GLOBAL_RULES_CANDIDATES:
        candidate = plan.codex_home / filename
        if not regular_target(candidate, plan.codex_home, "global instructions", plan):
            continue
        try:
            if not candidate.is_file():
                plan.current.append((candidate, "managed global-rules block already absent"))
                continue
            content = candidate.read_bytes()
        except OSError as error:
            plan.conflicts.append(f"global instructions unreadable: {candidate}: {error}")
            continue
        state, ranges = contract.managed_global_rules_ranges(content)
        if state == "corrupt" or len(ranges) > 1:
            plan.conflicts.append(f"global rules markers corrupt or duplicated: {candidate}")
            continue
        if not ranges:
            plan.current.append((candidate, "managed global-rules block already absent"))
            continue
        start, end = ranges[0]
        plan.add_write(
            candidate,
            content[:start] + content[end:],
            "remove managed global-rules block",
            expected=content,
            use_expected=True,
        )


def initialize_plan(codex_home: Path, skills_root: Path) -> tuple[InstallPlan, bool]:
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
        return plan, False
    home_ok = ensure_physical_root(codex_home, "Codex home", plan)
    skills_ok = ensure_physical_root(skills_root, "Skill root", plan)
    return plan, home_ok and skills_ok


def build_plan(
    codex_home: Path,
    skills_root: Path,
    *,
    language: str | None,
    global_rules: bool,
) -> InstallPlan:
    plan, roots_ok = initialize_plan(codex_home, skills_root)
    if not roots_ok:
        return plan

    for name, source_root in contract.BUNDLED_SKILLS.items():
        plan_skill(plan, name, source_root, plan.skills_root / name)
    plan_agents(plan)
    plan_preferences(plan, language)
    inspect_model_routing(plan)
    if global_rules:
        plan_global_rules(plan)
    else:
        check_unchanged_global_rules(plan)
    return plan


def inspect_model_routing(plan: InstallPlan) -> None:
    target = plan.codex_home / "codex-orchestration" / "model-routing.toml"
    plan.model_routing_path = target
    if not regular_target(target, plan.codex_home, "local model routing", plan):
        plan.model_routing_state = "conflict"
        return
    if not target.is_file():
        plan.model_routing_state = "absent"
        return
    try:
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        plan.conflicts.append(f"local model routing unreadable: {target}: {error}")
        plan.model_routing_state = "conflict"
        return
    failures = contract.model_routing_failures(source, allow_placeholders=False)
    if failures:
        plan.conflicts.extend(
            f"local model routing invalid: {target}: {failure}" for failure in failures
        )
        plan.model_routing_state = "conflict"
        return
    plan.model_routing_state = "present"


def build_uninstall_plan(codex_home: Path, skills_root: Path) -> InstallPlan:
    plan, roots_ok = initialize_plan(codex_home, skills_root)
    if not roots_ok:
        return plan
    for label, selected_root in (
        ("Codex home", plan.codex_home),
        ("Skill root", plan.skills_root),
    ):
        if paths_overlap(selected_root, ROOT):
            plan.conflicts.append(
                f"{label} overlaps source checkout; refusing uninstall: {selected_root}"
            )
    if plan.conflicts:
        return plan
    for name, source_root in contract.BUNDLED_SKILLS.items():
        plan_skill_removal(plan, name, source_root, plan.skills_root / name)
    plan_agent_removal(plan)
    plan_preferences_removal(plan)
    plan_global_rules_removal(plan)
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
    staged_deletions: dict[Path, Path] | None = None,
) -> list[str]:
    failures: list[str] = []
    staged_deletions = staged_deletions or {}
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
            if operation.content is None and operation.path in staged_deletions:
                temporary = staged_deletions[operation.path]
                if lexists(operation.path):
                    failures.append(f"rollback refused changed target: {operation.path}")
                    continue
                if not regular_target(temporary, root, "rollback staged deletion", probe):
                    failures.append(
                        f"rollback refused conflicting staged deletion: {temporary}: "
                        f"{probe.conflicts[-1]}"
                    )
                    continue
                if not temporary.is_file() or temporary.read_bytes() != old_content:
                    failures.append(f"rollback refused changed staged deletion: {temporary}")
                    continue
                os.replace(temporary, operation.path)
                continue
            current = operation.path.read_bytes() if operation.path.is_file() else None
            installed = operation.content
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


def managed_runtime_targets(plan: InstallPlan) -> list[Path]:
    targets: list[Path] = []
    for name, source_root in contract.BUNDLED_SKILLS.items():
        target_root = plan.skills_root / name
        targets.extend(
            target_root / source.relative_to(source_root)
            for source in source_skill_files(name, source_root)
        )
    targets.extend(
        plan.codex_home / "agents" / source.name
        for source in sorted((ROOT / "agents").glob("*.toml"))
    )
    targets.append(plan.codex_home / "codex-orchestration" / "preferences.toml")
    return targets


def uninstall_verification_failures(plan: InstallPlan) -> list[str]:
    failures = contract.validate_source()
    for target in managed_runtime_targets(plan):
        if lexists(target):
            failures.append(f"managed runtime target remains after uninstall: {target}")
    for filename in GLOBAL_RULES_CANDIDATES:
        candidate = plan.codex_home / filename
        try:
            if not candidate.is_file():
                continue
            content = candidate.read_bytes()
        except OSError as error:
            failures.append(f"global instructions unreadable after uninstall: {candidate}: {error}")
            continue
        state, ranges = contract.managed_global_rules_ranges(content)
        if state == "corrupt":
            failures.append(f"global rules markers corrupt after uninstall: {candidate}")
        elif ranges:
            failures.append(f"managed global-rules block remains after uninstall: {candidate}")
    return failures


def verification_failures(
    plan: InstallPlan, *, global_rules: bool, uninstall: bool = False
) -> list[str]:
    if uninstall:
        return uninstall_verification_failures(plan)
    failures = contract.validate_source()
    failures.extend(contract.validate_runtime(plan.codex_home, plan.skills_root))
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
    recheck_snapshot(plan, operation.path, operation.expected, "transaction target")


def cleanup_empty_managed_directories(plan: InstallPlan, deleted_paths: list[Path]) -> None:
    owned_roots = [
        *(plan.skills_root / name for name in contract.BUNDLED_SKILLS),
        plan.codex_home / "codex-orchestration",
    ]
    candidates: set[Path] = set()
    for path in deleted_paths:
        for owned_root in owned_roots:
            if not path.is_relative_to(owned_root):
                continue
            current = path.parent
            while current.is_relative_to(owned_root):
                candidates.add(current)
                if current == owned_root:
                    break
                current = current.parent
    for directory in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def apply_plan(plan: InstallPlan, *, global_rules: bool, uninstall: bool = False) -> list[str]:
    if plan.conflicts:
        raise RuntimeError("installation plan has conflicts")
    previous: dict[Path, bytes | None] = {}
    completed: list[Operation] = []
    created_directories: list[Path] = []
    staged_deletions: dict[Path, Path] = {}
    try:
        for operation in plan.operations:
            recheck_operation(plan, operation)
            previous[operation.path] = operation.expected
            if operation.content is None:
                temporary = installer_temporary_path(operation.path, secrets.token_hex(12))
                recheck_snapshot(plan, temporary, None, "staged deletion")
                completed.append(operation)
                os.replace(operation.path, temporary)
                staged_deletions[operation.path] = temporary
                recheck_snapshot(plan, operation.path, None, "post-delete target")
            else:
                create_parent_directories(operation.path, created_directories)
                completed.append(operation)
                atomic_write(operation.path, operation.content)
                recheck_snapshot(plan, operation.path, operation.content, "post-write target")
        failures = verification_failures(plan, global_rules=global_rules, uninstall=uninstall)
        if failures:
            details = "\n".join(f"- {item}" for item in failures)
            raise RuntimeError(f"verification failed:\n{details}")
    except BaseException as error:
        rollback_failures = rollback(
            plan,
            completed,
            previous,
            created_directories,
            staged_deletions,
        )
        if rollback_failures:
            raise RuntimeError(f"{error}\n" + "\n".join(rollback_failures)) from error
        raise
    warnings: list[str] = []
    for temporary in staged_deletions.values():
        try:
            temporary.unlink()
        except OSError as error:
            warnings.append(
                "staged uninstall copy could not be removed after verified commit; inspect and "
                f"remove it manually: {temporary}: {error}"
            )
    cleanup_empty_managed_directories(plan, list(staged_deletions))
    return warnings


def print_plan(plan: InstallPlan, *, global_rules: bool, uninstall: bool = False) -> None:
    action = "uninstall" if uninstall else "installation"
    print(f"Codex Orchestration {action} plan")
    print(f"Codex home: {plan.codex_home}")
    print(f"Skill root: {plan.skills_root}")
    if uninstall:
        print("Global rules: remove managed block")
    else:
        print(f"Global rules: {'managed block' if global_rules else 'unchanged'}")
        routing_path = plan.model_routing_path
        if plan.model_routing_state == "present":
            print(f"Model routing: preserve validated local configuration: {routing_path}")
        elif plan.model_routing_state == "absent":
            print(
                "Model routing: not configured; subagents request inheritance from current "
                "Codex settings (resolved model unconfirmed)"
            )
            print(
                "Optional model routing requires live host-model verification and explicit "
                f"approval before creating: {routing_path}"
            )
        elif plan.model_routing_state == "conflict":
            print(f"Model routing: invalid or conflicting local path: {routing_path}")
    for operation in plan.operations:
        if operation.content is None:
            label = "DELETE"
            digest = f" sha256={sha256_bytes(operation.expected or b'')}"
        else:
            label = "UPDATE" if operation.path.is_file() else "CREATE"
            digest = f" sha256={sha256_bytes(operation.content)}"
        print(f"[{label}] {operation.path} — {operation.reason}{digest}")
    if not plan.operations:
        state = "already absent" if uninstall else "no managed runtime changes"
        print(f"[CURRENT] {state}")
    if not uninstall and global_rules and plan.global_rules_target is not None:
        print(f"Active global instructions: {plan.global_rules_target}")
        print(contract.GLOBAL_RULES_TEMPLATE.read_text(encoding="utf-8").rstrip())
    for conflict in plan.conflicts:
        print(f"[CONFLICT] {conflict}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
        help="active Codex home (default: CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        help="Codex user Skill root (default: <codex-home>/skills)",
    )
    parser.add_argument(
        "--language",
        choices=sorted(contract.TASK_PACKAGE_LANGUAGES),
        help="task-package language; prompted on an interactive first install",
    )
    parser.add_argument(
        "--global-rules",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="inject the managed global AGENTS block during install (default: enabled)",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the current managed global runtime projection",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply the displayed plan without an interactive confirmation",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, interactive: bool | None = None) -> int:
    args = parse_args(argv)
    source_failures = contract.validate_source()
    if source_failures:
        for failure in source_failures:
            print(f"FAIL: {failure}")
        return 1
    codex_home = args.codex_home.expanduser().absolute()
    skills_root = (args.skills_root or codex_home / "skills").expanduser().absolute()
    if interactive is None:
        interactive = interactive_terminal()
    if args.uninstall and args.language is not None:
        print("Refusing uninstall because --language applies only to installation.")
        return 2
    if args.uninstall and not args.global_rules:
        print("Refusing uninstall because --no-global-rules would leave unusable global routing.")
        return 2
    preferences_path = codex_home / "codex-orchestration" / "preferences.toml"
    if (
        not args.uninstall
        and args.language is None
        and interactive
        and not lexists(preferences_path)
    ):
        args.language = prompt_task_package_language(detected_task_package_language())
        if args.language is None:
            print("Installation cancelled; no files changed.")
            return 0
    if args.uninstall:
        plan = build_uninstall_plan(codex_home, skills_root)
    else:
        plan = build_plan(
            codex_home,
            skills_root,
            language=args.language,
            global_rules=args.global_rules,
        )
    print_plan(plan, global_rules=args.global_rules, uninstall=args.uninstall)
    if plan.conflicts:
        action = "uninstall" if args.uninstall else "installation"
        print(f"Refusing {action} because the plan contains conflicts.")
        return 2
    if not args.apply:
        if not plan.operations:
            state = "already absent" if args.uninstall else "already current"
            print(f"OK: managed runtime is {state}")
            return 0
        if not interactive:
            print("Dry run only. Re-run the same command with --apply to write these changes.")
            return 0
        action = "uninstall" if args.uninstall else "installation"
        if not confirm_apply(action):
            print(f"{action.capitalize()} cancelled; no files changed.")
            return 0
    try:
        warnings = apply_plan(plan, global_rules=args.global_rules, uninstall=args.uninstall)
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}")
        return 1
    for warning in warnings:
        print(f"[WARNING] {warning}")
    if args.uninstall:
        print("OK: uninstall applied and managed runtime absence verified")
    else:
        print("OK: installation applied and runtime verification passed")
    print("Start a new Codex task so Skills, Agents, and global rules reload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
