from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.py"


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
                                {"hooks": [{"type": "command", "command": "foreign-hook"}]}
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
            skill = codex_home / "skills" / "codex-orchestration"
            self.assertTrue(skill.is_symlink())
            self.assertEqual(skill.resolve(), ROOT)
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
            self.assertTrue(any("orchestration_route.py" in command for command in commands))
            self.assertTrue(any("subagent_scope.py" in command for command in commands))

            second = self.run_installer(codex_home, "--apply", "--with-hooks")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertNotIn("CREATED:", second.stdout)
            self.assertNotIn("UPDATED:", second.stdout)

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
