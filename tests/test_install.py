from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.py"
SKILL_SOURCES = {
    "codex-orchestration": ROOT,
    "diagnosing-bugs": ROOT / "skills" / "diagnosing-bugs",
    "prototype": ROOT / "skills" / "prototype",
}


class InstallerTest(unittest.TestCase):
    def run_installer(self, codex_home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), "--codex-home", str(codex_home), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_dry_run_apply_hooks_and_idempotence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            codex_home.mkdir()
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {"type": "command", "command": "foreign-hook"},
                                        {
                                            "type": "command",
                                            "command": "python /tmp/orchestration_route.py-wrapper",
                                        },
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            dry_run = self.run_installer(codex_home, "--with-hooks")
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
            self.assertIn("WOULD CREATE skill link", dry_run.stdout)

            applied = self.run_installer(codex_home, "--apply", "--with-hooks")
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            for name, source in SKILL_SOURCES.items():
                skill = codex_home / "skills" / name
                self.assertTrue(skill.is_symlink())
                self.assertEqual(skill.resolve(), source)
            self.assertEqual(
                len(list((codex_home / "agents").glob("*.toml"))),
                len(list((ROOT / "agents").glob("*.toml"))),
            )
            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for groups in hooks["hooks"].values()
                for group in groups
                for hook in group.get("hooks", [])
            ]
            self.assertIn("foreign-hook", commands)
            self.assertIn("python /tmp/orchestration_route.py-wrapper", commands)
            self.assertTrue(any("orchestration_route.py" in command for command in commands))
            self.assertTrue(any("subagent_scope.py" in command for command in commands))

            second = self.run_installer(codex_home, "--apply", "--with-hooks")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertNotIn("CREATED:", second.stdout)
            self.assertNotIn("UPDATED:", second.stdout)

    def test_existing_method_skill_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            existing = codex_home / "skills" / "diagnosing-bugs"
            existing.mkdir(parents=True)
            skill_file = existing / "SKILL.md"
            skill_file.write_text(
                '---\nname: "diagnosing-bugs"\n---\n\n# Existing installation\n',
                encoding="utf-8",
            )

            applied = self.run_installer(codex_home, "--apply")

            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertIn("REUSE existing skill: diagnosing-bugs", applied.stdout)
            self.assertFalse(existing.is_symlink())
            self.assertIn("Existing installation", skill_file.read_text(encoding="utf-8"))
            self.assertTrue((codex_home / "skills" / "codex-orchestration").is_symlink())
            self.assertTrue((codex_home / "skills" / "prototype").is_symlink())

    def test_skill_conflict_fails_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            conflict = codex_home / "skills" / "prototype"
            conflict.mkdir(parents=True)
            (conflict / "SKILL.md").write_text(
                "---\nname: prototype\n---not-a-delimiter\n\n# Invalid frontmatter\n",
                encoding="utf-8",
            )

            refused = self.run_installer(codex_home, "--apply")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("REFUSED skill conflict: prototype", refused.stdout)
            self.assertFalse((codex_home / "skills" / "codex-orchestration").exists())
            self.assertFalse((codex_home / "skills" / "diagnosing-bugs").exists())
            self.assertFalse((codex_home / "agents").exists())

    def test_drift_fails_before_any_install_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            drift = codex_home / "agents" / "explorer.toml"
            drift.parent.mkdir(parents=True)
            drift.write_text("drift\n", encoding="utf-8")
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_text('{"hooks": {}}\n', encoding="utf-8")
            original_hooks = hooks_path.read_bytes()

            refused = self.run_installer(codex_home, "--apply", "--with-hooks")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("REFUSED drift", refused.stdout)
            self.assertFalse((codex_home / "skills").exists())
            self.assertEqual(list((codex_home / "agents").iterdir()), [drift])
            self.assertFalse((codex_home / "hooks").exists())
            self.assertEqual(hooks_path.read_bytes(), original_hooks)

    def test_directory_file_conflict_fails_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            conflict = codex_home / "agents" / "explorer.toml"
            conflict.mkdir(parents=True)

            refused = self.run_installer(codex_home, "--apply")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("REFUSED file conflict", refused.stdout)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse((codex_home / "skills").exists())

    def test_parent_file_conflict_fails_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            codex_home.mkdir()
            (codex_home / "agents").write_text("not a directory\n", encoding="utf-8")

            refused = self.run_installer(codex_home, "--apply")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("REFUSED file conflict", refused.stdout)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse((codex_home / "skills").exists())

    def test_non_utf8_skill_conflicts_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            conflict = codex_home / "skills" / "prototype"
            conflict.mkdir(parents=True)
            (conflict / "SKILL.md").write_bytes(b"\xff")

            refused = self.run_installer(codex_home, "--apply")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("REFUSED skill conflict: prototype", refused.stdout)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse((codex_home / "agents").exists())

    def test_replace_external_skill_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home = temporary_path / "codex-home"
            external = temporary_path / "external-prototype"
            external.mkdir()
            (external / "SKILL.md").write_text(
                "---\nname: prototype\n---\n",
                encoding="utf-8",
            )
            target = codex_home / "skills" / "prototype"
            target.parent.mkdir(parents=True)
            target.symlink_to(external, target_is_directory=True)

            replaced = self.run_installer(codex_home, "--apply", "--replace")

            self.assertEqual(replaced.returncode, 0, replaced.stdout + replaced.stderr)
            self.assertEqual(target.resolve(), SKILL_SOURCES["prototype"])

    def test_drift_requires_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            applied = self.run_installer(codex_home, "--apply")
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            target = codex_home / "agents" / "explorer.toml"
            target.write_text("drift\n", encoding="utf-8")

            refused = self.run_installer(codex_home, "--apply")
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "drift\n")

            replaced = self.run_installer(codex_home, "--apply", "--replace")
            self.assertEqual(replaced.returncode, 0, replaced.stdout + replaced.stderr)
            self.assertEqual(target.read_bytes(), (ROOT / "agents" / "explorer.toml").read_bytes())

    def test_routing_config_must_be_customized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            codex_home = temporary_path / "codex-home"
            example = ROOT / "examples" / "model-routing.toml"

            refused = self.run_installer(codex_home, "--apply", "--routing-config", str(example))
            self.assertEqual(refused.returncode, 1)
            self.assertIn("placeholder", refused.stdout)

            custom = temporary_path / "routing.toml"
            custom.write_text(
                example.read_text(encoding="utf-8")
                .replace("MODEL_ID_PRIMARY", "available-primary")
                .replace("MODEL_ID_FALLBACK", "available-fallback")
                .replace("REASONING_LEVEL", "high")
                .replace("SERVICE_TIER", "priority"),
                encoding="utf-8",
            )
            applied = self.run_installer(codex_home, "--apply", "--routing-config", str(custom))
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            target = codex_home / "codex-orchestration" / "model-routing.toml"
            self.assertEqual(target.read_bytes(), custom.read_bytes())

    def test_invalid_hooks_config_fails_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / "codex-home"
            codex_home.mkdir()
            (codex_home / "hooks.json").write_text("{invalid", encoding="utf-8")

            refused = self.run_installer(codex_home, "--apply", "--with-hooks")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("INVALID hooks config", refused.stdout)
            self.assertFalse((codex_home / "skills" / "codex-orchestration").exists())
            self.assertFalse((codex_home / "agents").exists())


if __name__ == "__main__":
    unittest.main()
