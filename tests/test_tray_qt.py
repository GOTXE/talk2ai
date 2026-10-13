import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PyQt6.QtCore import QFileSystemWatcher
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - exercised in CI only when PyQt6 is installed
    QFileSystemWatcher = None
    QApplication = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from talk2ai_debug_log import DebugLogReader, serialize_event  # noqa: E402


@unittest.skipIf(QApplication is None, "PyQt6 is not installed")
class TrayWatcherIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        loader = importlib.machinery.SourceFileLoader(
            "talk2ai_tray_for_tests",
            str(Path(__file__).resolve().parents[1] / "scripts" / "talk2ai-tray"),
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.tray_module = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.tray_module)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.log = self.root / "debug.log"
        self.tray_module.TALK2AI_DIR = self.root
        self.tray_module.DEBUG_LOG_FILE = self.log
        self.reader = DebugLogReader()
        self.records = []

        class Window:
            def isVisible(window_self):
                return True

            def _read_new_lines(window_self):
                records, _ = self.reader.read_new(self.log)
                self.records.extend(records)

        self.tray = self.tray_module.TalkTray.__new__(self.tray_module.TalkTray)
        self.tray._debug_window = Window()
        self.watcher = QFileSystemWatcher([str(self.root)])
        self.tray._watcher = self.watcher
        self.watcher.fileChanged.connect(self.tray._on_file_changed)
        self.watcher.directoryChanged.connect(self.tray._on_directory_changed)

    def tearDown(self):
        self.watcher.deleteLater()
        self.directory.cleanup()

    def wait_for_records(self, expected_count):
        deadline = time.monotonic() + 3
        while len(self.records) < expected_count and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertGreaterEqual(len(self.records), expected_count)

    def assert_log_watched(self):
        self.assertIn(str(self.log), self.watcher.files())

    def make_toggle_tray(self):
        class Action:
            def __init__(action_self):
                action_self.checked = None

            def setChecked(action_self, checked):
                action_self.checked = checked

        class Tray:
            def __init__(tray_self):
                tray_self.messages = []

            def showMessage(tray_self, *message):
                tray_self.messages.append(message)

        tray = self.tray_module.TalkTray.__new__(self.tray_module.TalkTray)
        tray.act_debug = Action()
        tray.tray = Tray()
        tray._watcher = self.watcher
        tray._debug_window = None
        return tray

    def test_toggle_debug_keeps_disabled_when_clear_times_out_and_recovers(self):
        self.tray_module.DEBUG_ENABLED_FILE = self.root / "debug"
        tray = self.make_toggle_tray()
        with patch.object(self.tray_module, "clear_log", side_effect=TimeoutError("busy")):
            tray._toggle_debug(True)
        self.assertFalse(self.tray_module.DEBUG_ENABLED_FILE.exists())
        self.assertFalse(tray.act_debug.checked)
        self.assertEqual(len(tray.tray.messages), 1)

        with patch.object(self.tray_module, "clear_log"):
            tray._toggle_debug(True)
        self.assertTrue(self.tray_module.DEBUG_ENABLED_FILE.exists())
        self.assertTrue(tray.act_debug.checked)

    def test_toggle_debug_keeps_marker_and_menu_consistent_on_os_error(self):
        self.tray_module.DEBUG_ENABLED_FILE = self.root / "debug"
        self.tray_module.DEBUG_ENABLED_FILE.touch()
        tray = self.make_toggle_tray()
        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            tray._toggle_debug(False)
        self.assertTrue(self.tray_module.DEBUG_ENABLED_FILE.exists())
        self.assertTrue(tray.act_debug.checked)
        self.assertEqual(len(tray.tray.messages), 1)

    def test_debug_window_reports_clear_error_without_losing_visible_log(self):
        window = self.tray_module.DebugWindow()
        window.text.setPlainText("registro visible")
        with patch.object(self.tray_module, "clear_log", side_effect=PermissionError("denied")):
            window._clear()
        self.assertEqual(window.text.toPlainText(), "registro visible")
        window.close()

    def test_watcher_recovers_after_replace_delete_recreate_and_rotation(self):
        self.log.write_bytes(serialize_event(1, "A", "normal").encode())
        self.tray._watch_debug_log()
        self.assert_log_watched()
        self.wait_for_records(1)

        replacement = self.root / "debug.log.new"
        replacement.write_bytes(serialize_event(2, "A", "reemplazado").encode())
        os.replace(replacement, self.log)
        with self.log.open("ab") as stream:
            stream.write(serialize_event(3, "A", "inmediato").encode())
        self.wait_for_records(3)
        self.assert_log_watched()

        self.log.unlink()
        self.wait_for_records(3)
        self.log.write_bytes(serialize_event(4, "A", "recreado").encode())
        self.wait_for_records(4)
        self.assert_log_watched()

        rotated = self.root / "debug.log.1"
        os.replace(self.log, rotated)
        self.log.write_bytes(serialize_event(5, "A", "rotado").encode())
        self.wait_for_records(5)
        self.assert_log_watched()
        self.assertEqual([record[2] for record in self.records],
                         ["normal", "reemplazado", "inmediato", "recreado", "rotado"])


if __name__ == "__main__":
    unittest.main()
