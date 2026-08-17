#!/usr/bin/env python3
"""Validate the public source contract and optional local runtime."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
        "version: 0.1.0",
        "references/model-routing.md",
        "references/worker-writing.md",
        "coverage",
        "panel",
        "hybrid",
        "Single writer",
        "Do not create a worktree unless the user explicitly requests one",
    ):
        require(phrase in skill, f"missing Skill contract: {phrase}", failures)

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
    skill_target = codex_home / "skills" / "codex-orchestration"
    require(
        skill_target.is_symlink() and skill_target.resolve() == ROOT,
        "runtime skill link differs",
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
