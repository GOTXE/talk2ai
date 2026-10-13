"""Regression tests for files that are distributed to users' home directories."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class PortableInstallTest(unittest.TestCase):
    def test_distributed_code_has_no_developer_paths(self):
        """Reject machine-specific paths without flagging intentional docs/tests."""
        files = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=REPO, text=True
        ).split("\0")
        offenders = []
        forbidden = ("/home/gtx", "Documentos/Prog_Local/handy-gemini-tts", "/tmp/handy-mode")
        for relative in files:
            if not relative or relative.startswith(("docs/", "tests/", "README")):
                continue
            path = REPO / relative
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(value in text for value in forbidden):
                offenders.append(relative)
        self.assertEqual(offenders, [], f"rutas locales distribuidas: {offenders}")

    def test_installed_tts_uses_deployed_data_after_checkout_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # These are isolated HOME directories (not login accounts), which
            # proves the installed executable has no dependency on the real
            # checkout, UID, or the invoking developer's home directory.
            for label in ("alice", "testuser", "custom/location/for/home"):
                with self.subTest(home=label):
                    home = root / label
                    bin_dir = home / ".local" / "bin"
                    state = home / ".talk2ai"
                    data = root / "data" / label / "talk2ai"
                    runtime = root / "runtime" / label
                    bin_dir.mkdir(parents=True)
                    data.mkdir(parents=True)
                    runtime.mkdir(parents=True)
                    installed = bin_dir / "talk2ai-tts"
                    shutil.copy2(REPO / "scripts" / "talk2ai-tts", installed)
                    installed.chmod(0o755)
                    for name in ("tts-catalog.json", "tts-artifacts.json"):
                        shutil.copy2(REPO / "config" / name, data / name)

                    environment = {
                        **os.environ,
                        "HOME": str(home),
                        "TALK2AI_DIR": str(state),
                        "TALK2AI_DATA_DIR": str(data),
                        "XDG_RUNTIME_DIR": str(runtime),
                    }
                    result = subprocess.run(
                        [str(installed), "list", "--json"], env=environment,
                        text=True, capture_output=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    profiles = {item["id"] for item in json.loads(result.stdout)}
                    self.assertIn("espeak-retro", profiles)

    def test_installer_updates_versioned_tts_data_but_keeps_preferences(self):
        installer = (REPO / "install.sh").read_text(encoding="utf-8")
        self.assertIn('install -m 0644 "$REPO_DIR/config/$tts_config" "$TTS_DATA_DIR/$tts_config"', installer)
        self.assertIn('[ -f "$TALK2AI_DIR/tts-engine" ] ||', installer)
        self.assertIn('[ -f "$TALK2AI_DIR/tts-voice" ] ||', installer)
        self.assertIn('[ -f "$TALK2AI_DIR/tts-speed" ] ||', installer)


if __name__ == "__main__":
    unittest.main()
