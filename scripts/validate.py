#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import os
import re
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
    worker_contract = (ROOT / "references" / "worker-writing.md").read_text(encoding="utf-8")

    for phrase in (
        "version: 0.2.0",
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

    for path in public_text_files():
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_PUBLIC_PATTERNS.items():
            require(pattern not in text, f"{label} in {path.relative_to(ROOT)}", failures)

    installer = (ROOT / "scripts" / "install.py").read_text(encoding="utf-8")
    require('sys.platform != "darwin"' in installer, "installer is not macOS-gated", failures)
    require(
        "MODEL_ID_PRIMARY"
        in (ROOT / "examples" / "model-routing.toml").read_text(encoding="utf-8"),
        "routing example lost placeholders",
        failures,
    )
    return failures


def validate_runtime(codex_home: Path) -> list[str]:
    failures: list[str] = []
    for name in BUNDLED_SKILLS:
        skill_target = codex_home / "skills" / name / "SKILL.md"
        try:
            installed = skill_target.read_text(encoding="utf-8") if skill_target.is_file() else ""
        except (OSError, UnicodeError):
            installed = ""
        require(
            skill_document_name(installed) == name,
            f"runtime Skill missing or mismatched: {name}",
            failures,
        )
    for source in sorted((ROOT / "agents").glob("*.toml")):
        target = codex_home / "agents" / source.name
        require(
            target.is_file() and target.read_bytes() == source.read_bytes(),
            f"runtime agent differs: {target}",
            failures,
        )
    for source in sorted((ROOT / "hooks").glob("*.py")):
        target = codex_home / "hooks" / source.name
        if target.exists():
            require(
                target.read_bytes() == source.read_bytes(),
                f"runtime hook differs: {target}",
                failures,
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args()

    failures = validate_source()
    if args.runtime:
        configured = args.codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        failures.extend(validate_runtime(configured.expanduser().resolve()))
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: source contract; agents={len(WRITERS | READERS)}; platform=macOS")
    if args.runtime:
        print("OK: runtime skill and agents match source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
