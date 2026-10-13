import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from talk2ai_debug_log import (  # noqa: E402
    DebugLogReader,
    EVENT_TYPES,
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
