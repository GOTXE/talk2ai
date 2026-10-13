import json
import os
import http.server
import importlib.util
import importlib.machinery
import queue
import socket
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TTS = REPO / "scripts" / "talk2ai-tts"


def load_broker_module():
    loader = importlib.machinery.SourceFileLoader("talk2ai_tts_test_module", str(TTS))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TtsBrokerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.runtime = root / "runtime"
        self.runtime.mkdir()
        self.state = root / "state"
        self.data = root / "data"
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
                    "TALK2AI_DATA_DIR": str(self.data),
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

    def test_kokoro_is_not_advertised_without_a_real_validation(self):
        # Files and a placeholder interpreter do not validate Spanish G2P,
        # voice contents or actual playback.  Keep profiles unavailable until
        # a genuine runtime validation exists.
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
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no seleccionable", result.stderr)
        self.assertEqual((self.state / "tts-engine").read_text().strip(), "espeak-ng")

    def test_protocol_handles_fragmentation_and_rejects_late_turn(self):
        path = self.runtime / "talk2ai-tts.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(str(path))
            client.sendall(b'{"command":"status"}')
            # No delimiter means no request, even if recv boundaries change.
            client.sendall(b'\n')
            reply = client.makefile("rb").readline()
        self.assertTrue(json.loads(reply)["ok"])

        generation = int((self.state / "tts-cancel-generation").read_text())
        self.assertEqual(self.run_tts("cancel").returncode, 0)
        late = self.run_tts("speak", "--generation", str(generation), input_text="no debe sonar")
        self.assertNotEqual(late.returncode, 0)
        self.assertIn("cancelado", late.stderr)

    def test_socket_is_private_and_espeak_rejects_kokoro_speed_units(self):
        socket_path = self.runtime / "talk2ai-tts.sock"
        self.assertEqual(stat.S_IMODE(socket_path.stat().st_mode), 0o600)
        # A stale neural multiplier must not become eSpeak's 1 WPM.
        (self.state / "tts-speed").write_text("1.0\n")
        self.assertEqual(self.run_tts("speak", input_text="velocidad segura").returncode, 0)
        for _ in range(50):
            if self.log.exists():
                break
            time.sleep(0.02)
        self.assertIn("-s 140", self.log.read_text())

    def test_speed_is_validated_in_engine_specific_units_and_persisted(self):
        self.assertEqual(self.run_tts("speed", "180").returncode, 0)
        self.assertEqual((self.state / "tts-speed").read_text().strip(), "180")
        rejected = self.run_tts("speed", "1.0")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("fuera de rango", rejected.stderr)

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
            manifest_path = self.data / "tts-artifacts.json"
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

    def test_cancel_and_enqueue_are_atomic_and_never_leave_old_generation(self):
        module = load_broker_module()
        with mock.patch.object(module, "ROOT", self.state), mock.patch.object(module, "atomic_write"):
            broker = module.Broker()
            profile = {"engine": "espeak-ng", "voice": "es"}
            barrier = threading.Barrier(3)

            def enqueue():
                barrier.wait()
                try:
                    broker.enqueue("fragmento", profile)
                except RuntimeError:
                    pass

            def cancel():
                barrier.wait()
                broker.cancel()

            producer = threading.Thread(target=enqueue)
            canceller = threading.Thread(target=cancel)
            producer.start()
            canceller.start()
            barrier.wait()
            producer.join(timeout=2)
            canceller.join(timeout=2)
            self.assertFalse(producer.is_alive())
            self.assertFalse(canceller.is_alive())
            queued = []
            while True:
                try:
                    queued.append(broker.requests.get_nowait())
                except queue.Empty:
                    break
            self.assertTrue(all(item[2] == broker.generation for item in queued))

    def test_cancel_between_extraction_and_playback_rejects_stale_generation(self):
        module = load_broker_module()
        with mock.patch.object(module, "ROOT", self.state), mock.patch.object(module, "atomic_write"):
            broker = module.Broker()
            profile = {"engine": "espeak-ng", "voice": "es"}
            generation = broker.enqueue("no debe reproducirse", profile)
            broker.cancel()
            with mock.patch.object(module, "availability", return_value=(True, "")), \
                    mock.patch.object(broker, "invoke") as invoke:
                with self.assertRaisesRegex(RuntimeError, "cancelada"):
                    broker.speak("no debe reproducirse", profile, generation)
                invoke.assert_not_called()

    def test_second_broker_cannot_take_an_active_socket(self):
        second = subprocess.run([str(TTS), "serve"], env=self.env, text=True,
                                capture_output=True, timeout=4)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("instancia activa", second.stderr)

    def test_broker_restart_preserves_cancel_generation(self):
        self.assertEqual(self.run_tts("cancel").returncode, 0)
        generation = int((self.state / "tts-cancel-generation").read_text())
        self.server.terminate()
        self.server.wait(timeout=3)
        self.server = subprocess.Popen([str(TTS), "serve"], env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        late = self.run_tts("speak", "--generation", str(generation - 1),
                            input_text="respuesta antigua")
        self.assertNotEqual(late.returncode, 0)
        self.assertIn("cancelado", late.stderr)


class DistributedFilesTest(unittest.TestCase):
    def test_no_developer_paths_or_legacy_state_paths_are_distributed(self):
        forbidden = ("/home/gtx", "Documentos/Prog_Local/handy-gemini-tts", "/tmp/handy-mode")
        # Tests may deliberately name forbidden values as fixtures; inspect
        # only files shipped to users so the guard has no self false-positive.
        for relative in ("config", "scripts", "install.sh", "README.md", "docs"):
            path = REPO / relative
            files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
            for item in files:
                if item.suffix in {".gif", ".webm", ".png", ".svg"}:
                    continue
                content = item.read_text(encoding="utf-8", errors="ignore")
                for value in forbidden:
                    self.assertNotIn(value, content, f"{value} en {item.relative_to(REPO)}")

    def test_kokoro_uses_spanish_phonemes_not_legacy_language_alias(self):
        worker = (REPO / "scripts" / "talk2ai-tts-kokoro").read_text(encoding="utf-8")
        self.assertIn('EspeakG2P(language="es")', worker)
        self.assertIn("is_phonemes=True", worker)
        self.assertNotIn('lang="e"', worker)

    def test_daemon_never_uses_unbound_tail_or_error_fallback(self):
        daemon = (REPO / "scripts" / "talk2ai-daemon").read_text(encoding="utf-8")
        self.assertIn('_speak "$_spoken_tail" "$_turn_generation"', daemon)
        self.assertIn('_speak "$_rand_msg" "$_turn_generation"', daemon)
        self.assertNotIn('_speak "$_spoken_tail"\n', daemon)


if __name__ == "__main__":
    unittest.main()
