import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from talk2ai_debug_log import (  # noqa: E402
    DebugLogReader,
    EVENT_TYPES,
    clear_log,
    parse_complete_records,
    parse_record_line,
    serialize_event,
    write_event,
)


class DebugLogTest(unittest.TestCase):
    def test_jsonl_preserves_multiline_unicode_and_special_characters(self):
        original = 'Buenos días.\n\n¿Cómo estás, ñandú? \'Muy bien!\' "sí" \\ | final'
        line = serialize_event(1791910000000, "A", original)
        self.assertEqual(parse_record_line(line.rstrip("\n")), (1791910000000, "A", original))
        self.assertEqual(len(line.splitlines()), 1)
        self.assertEqual(json.loads(line)["text"], original)

    def test_all_event_types_and_legacy_records(self):
        self.assertEqual(EVENT_TYPES, {"SEP", "INFO", "Q", "A", "L", "D"})
        for event_type in EVENT_TYPES:
            self.assertEqual(parse_record_line(f"123|{event_type}|texto|con|barras"),
                             (123, event_type, "texto|con|barras"))
        self.assertEqual(parse_record_line("123|A|línea antigua"), (123, "A", "línea antigua"))

    def test_mixed_log_and_malformed_or_incomplete_records(self):
        data = (
            b'123|Q|pregunta\n'
            + serialize_event(124, "A", "respuesta\n\nfinal").encode()
            + b'{"timestamp":125,"type":"A"}\n'
            + b'{"timestamp":126,"type":"A"'
        )
        records, pending = parse_complete_records(data)
        self.assertEqual(records, [(123, "Q", "pregunta"), (124, "A", "respuesta\n\nfinal")])
        self.assertEqual(pending, b'{"timestamp":126,"type":"A"')

        records, pending = parse_complete_records(pending + b'\n')
        self.assertEqual(records, [])
        self.assertEqual(pending, b"")

    def test_reader_waits_for_newline_and_recovers_after_truncate(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            log.write_bytes(b'123|A|parcial')
            reader = DebugLogReader()
            self.assertEqual(reader.read_new(log), ([], False))
            log.write_bytes(b'123|A|parcial\n')
            self.assertEqual(reader.read_new(log), ([(123, "A", "parcial")], False))
            log.write_bytes(b"")
            self.assertEqual(reader.read_new(log), ([], True))
            log.write_bytes(serialize_event(456, "D", "nuevo").encode())
            self.assertEqual(reader.read_new(log), ([(456, "D", "nuevo")], False))

    def test_clear_during_concurrent_writes_keeps_complete_post_clear_event(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            start = threading.Barrier(3)
            cleared = threading.Event()

            def write_before_clear(number):
                start.wait()
                write_event(log, number, "A", f"antes {number}\n" + "x" * 2000)

            def clear_while_writing():
                start.wait()
                clear_log(log)
                cleared.set()

            def write_after_clear():
                cleared.wait()
                write_event(log, 999, "D", "después de limpiar")

            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(write_before_clear, number) for number in (1, 2)]
                futures.append(pool.submit(clear_while_writing))
                for future in futures:
                    future.result()
                pool.submit(write_after_clear).result()

            records = [parse_record_line(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(all(record is not None for record in records))
            self.assertEqual(records.count((999, "D", "después de limpiar")), 1)

    def test_write_immediately_after_clear_is_visible_once(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            write_event(log, 1, "A", "anterior")
            clear_log(log)
            write_event(log, 2, "A", "posterior")
            reader = DebugLogReader()
            self.assertEqual(reader.read_new(log), ([(2, "A", "posterior")], False))
            self.assertEqual(reader.read_new(log), ([], False))

    def test_generation_detects_fast_growth_above_previous_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            write_event(log, 1, "A", "x" * 5000)
            reader = DebugLogReader()
            self.assertEqual(reader.read_new(log), ([(1, "A", "x" * 5000)], False))
            self.assertGreater(reader.offset, 5000)
            clear_log(log)
            write_event(log, 2, "A", "y" * 6000)
            records, truncated = reader.read_new(log)
            self.assertEqual(records, [(2, "A", "y" * 6000)])
            self.assertTrue(truncated)

    def test_replaced_log_is_detected_by_file_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            replacement = Path(directory) / "debug.log.rotated"
            write_event(log, 1, "A", "antiguo")
            reader = DebugLogReader()
            self.assertEqual(reader.read_new(log), ([(1, "A", "antiguo")], False))
            replacement.write_bytes(serialize_event(2, "A", "rotado").encode("utf-8"))
            os.chmod(replacement, 0o600)
            os.replace(replacement, log)
            self.assertEqual(reader.read_new(log), ([(2, "A", "rotado")], True))

    def test_reader_restart_with_pending_record(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            log.write_bytes(b"123|A|pendiente")
            first_reader = DebugLogReader()
            self.assertEqual(first_reader.read_new(log), ([], False))
            restarted_reader = DebugLogReader()
            self.assertEqual(restarted_reader.read_new(log), ([], False))
            with log.open("ab") as log_file:
                log_file.write(b"\n")
            self.assertEqual(restarted_reader.read_new(log), ([(123, "A", "pendiente")], False))

    def test_tray_uses_shared_clear_operation(self):
        tray_source = Path(__file__).parents[1] / "scripts" / "talk2ai-tray"
        source = tray_source.read_text(encoding="utf-8")
        self.assertIn("from talk2ai_debug_log import DebugLogReader, clear_log", source)
        self.assertNotIn("DEBUG_LOG_FILE.write_bytes", source)
        self.assertNotIn("DEBUG_LOG_FILE.write_text", source)

    def test_concurrent_writes_are_complete_records(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            events = [(i, "A", f"respuesta {i}\n" + "x" * 5000) for i in range(30)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda event: write_event(log, *event), events))
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), len(events))
            self.assertEqual({parse_record_line(line) for line in lines}, set(events))

    def test_cli_writer_is_the_same_real_serializer_used_by_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "debug.log"
            text = "¿Qué tal?\n\\ y \" |"
            subprocess.run(
                [sys.executable, str(Path(__file__).parents[1] / "scripts" / "talk2ai_debug_log.py"),
                 str(log), "789", "Q"],
                input=text, text=True, capture_output=True, check=True,
            )
            self.assertEqual(parse_record_line(log.read_text().rstrip("\n")), (789, "Q", text))


if __name__ == "__main__":
    unittest.main()
