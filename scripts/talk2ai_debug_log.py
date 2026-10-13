#!/usr/bin/env python3
"""Shared JSONL writer/parser for talk2ai's debug log."""

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

EVENT_TYPES = frozenset(("SEP", "INFO", "Q", "A", "L", "D"))


def serialize_event(timestamp, event_type, text):
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown debug event type: {event_type}")
    if not isinstance(text, str):
        raise TypeError("debug event text must be str")
    return json.dumps(
        {"timestamp": int(timestamp), "type": event_type, "text": text},
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"


def write_event(log_path, timestamp, event_type, text):
    payload = serialize_event(timestamp, event_type, text).encode("utf-8")
    log_path = Path(log_path)
    with Path(f"{log_path}.lock").open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def parse_record_line(line):
    """Parse one JSONL or legacy record; return (timestamp, type, text)."""
    if not line:
        return None
    try:
        if line.lstrip().startswith("{"):
            record = json.loads(line)
            if not isinstance(record, dict):
                return None
            timestamp = int(record["timestamp"])
            event_type = record["type"]
            text = record["text"]
            if event_type not in EVENT_TYPES or not isinstance(text, str):
                return None
            return timestamp, event_type, text
        timestamp, event_type, text = line.split("|", 2)
        if event_type not in EVENT_TYPES:
            return None
        return int(timestamp), event_type, text
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def parse_complete_records(data):
    """Parse complete physical lines and return (records, incomplete_bytes)."""
    complete, separator, pending = data.rpartition(b"\n")
    if not separator:
        return [], data
    records = []
    for raw_line in complete.split(b"\n"):
        try:
            record = parse_record_line(raw_line.decode("utf-8"))
        except UnicodeDecodeError:
            record = None
        if record is not None:
            records.append(record)
    return records, pending


class DebugLogReader:
    """Incrementally read JSONL/legacy records without consuming partial lines."""

    def __init__(self):
        self.offset = 0
        self.pending = b""

    def read_new(self, log_path):
        log_path = Path(log_path)
        size = log_path.stat().st_size
        truncated = size < self.offset
        if truncated:
            self.offset = 0
            self.pending = b""
        with log_path.open("rb") as log_file:
            log_file.seek(self.offset)
            chunk = log_file.read()
        self.offset += len(chunk)
        records, self.pending = parse_complete_records(self.pending + chunk)
        return records, truncated


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("log_path")
    parser.add_argument("timestamp", type=int)
    parser.add_argument("event_type", choices=sorted(EVENT_TYPES))
    args = parser.parse_args(argv)
    write_event(args.log_path, args.timestamp, args.event_type, sys.stdin.read())


if __name__ == "__main__":
    main()
