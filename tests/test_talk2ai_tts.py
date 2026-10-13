import json
import os
import http.server
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TTS = REPO / "scripts" / "talk2ai-tts"


class TtsBrokerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.runtime = root / "runtime"
        self.runtime.mkdir()
        self.state = root / "state"
        self.bin = root / "bin"
        self.bin.mkdir()
        self.log = root / "spoken.log"
        fake_espeak = self.bin / "espeak-ng"
        fake_espeak.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$TTS_TEST_LOG\"\n"
            "case \"$*\" in *SLOW*) sleep 10 ;; esac\n"
        )
        fake_espeak.chmod(0o755)
        self.env = {**os.environ, "TALK2AI_DIR": str(self.state),
                    "XDG_RUNTIME_DIR": str(self.runtime),
                    "TTS_TEST_LOG": str(self.log), "PATH": f"{self.bin}:{os.environ['PATH']}"}
        self.server = subprocess.Popen([str(TTS), "serve"], env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        socket_path = self.runtime / "talk2ai-tts.sock"
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.02)
        else:
            self.fail("el socket del broker no se creó")

    def tearDown(self):
        self.server.terminate()
        self.server.wait(timeout=3)
        self.temporary.cleanup()

    def run_tts(self, *args, input_text=""):
        return subprocess.run([str(TTS), *args], input=input_text, text=True, env=self.env,
                              capture_output=True, timeout=4)

    def test_previous_installation_defaults_to_retro(self):
        listing = self.run_tts("list", "--json")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        profiles = {profile["id"]: profile for profile in json.loads(listing.stdout)}
        self.assertTrue(profiles["espeak-retro"]["available"])
        self.assertFalse(profiles["piper-es-es-davefx-medium"]["available"])
        self.assertEqual((self.state / "tts-engine").read_text().strip(), "espeak-ng")
        self.assertEqual((self.state / "tts-voice").read_text().strip(), "es")

    def test_fifo_and_cancel_clear_active_and_queue(self):
        self.assertEqual(self.run_tts("speak", input_text="primera.").returncode, 0)
        self.assertEqual(self.run_tts("speak", input_text="segunda.").returncode, 0)
        for _ in range(100):
            if self.log.exists() and len(self.log.read_text().splitlines()) >= 2:
                break
            time.sleep(0.02)
        lines = self.log.read_text().splitlines()
        self.assertIn("primera.", lines[0])
        self.assertIn("segunda.", lines[1])
        self.assertEqual(self.run_tts("speak", input_text="SLOW").returncode, 0)
        time.sleep(0.1)
        self.assertEqual(self.run_tts("cancel").returncode, 0)
        self.assertEqual((self.state / "tts-state").read_text().strip(), "cancelled")

    def test_blocked_profile_cannot_be_selected_or_downloaded(self):
        selected = self.run_tts("select", "piper-es-es-sharvard-medium")
        self.assertNotEqual(selected.returncode, 0)
        self.assertIn("no seleccionable", selected.stderr)

    def test_kokoro_voice_selection_is_persistent_and_independent(self):
        # Availability is gated by both approved artifacts and the isolated
        # runtime; this does not require loading a real model in CI.
        model_dir = self.state / "tts" / "kokoro"
        model_dir.mkdir(parents=True)
        (model_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"fixture")
        (model_dir / "voices-v1.0.bin").write_bytes(b"fixture")
        runtime = self.state / "tts-venv" / "bin"
        runtime.mkdir(parents=True)
        python = runtime / "python"
        python.write_text("#!/bin/sh\nexit 0\n")
        python.chmod(0o755)
        for profile, voice in (("kokoro-ef-dora", "ef_dora"),
                               ("kokoro-em-alex", "em_alex"),
                               ("kokoro-em-santa", "em_santa")):
            result = self.run_tts("select", profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.state / "tts-voice").read_text().strip(), voice)
        self.assertEqual((self.state / "tts-engine").read_text().strip(), "kokoro-onnx")

    def test_optional_model_is_not_downloaded_without_confirmation(self):
        result = self.run_tts("download", "kokoro-ef-dora")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.state / "tts" / "kokoro").exists())

    def test_download_rejects_a_bad_hash_without_creating_model(self):
        served = Path(self.temporary.name) / "served"
        served.mkdir()
        (served / "artifact.bin").write_bytes(b"not-the-expected-model")

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(served), **kwargs)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            manifest_path = self.state / "tts-artifacts.json"
            manifest = json.loads(manifest_path.read_text())
            url = f"http://127.0.0.1:{server.server_port}/artifact.bin"
            for key in ("model", "voices"):
                manifest["kokoro"][key].update({"url": url, "sha256": "0" * 64})
            manifest_path.write_text(json.dumps(manifest))
            result = self.run_tts("download", "kokoro-ef-dora", "--confirm")
        finally:
            server.shutdown()
            server.server_close()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertFalse((self.state / "tts" / "kokoro" / "kokoro-v1.0.int8.onnx").exists())

    def test_text_is_not_executed_as_shell(self):
        marker = self.state / "must-not-exist"
        result = self.run_tts("speak", input_text=f"hola; touch {marker}")
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(0.1)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
