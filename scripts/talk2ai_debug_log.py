#!/usr/bin/env python3
"""Shared JSONL writer/parser for talk2ai's debug log."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

EVENT_TYPES = frozenset(("SEP", "INFO", "Q", "A", "L", "D"))


def _lock_path(log_path):
    return Path(f"{Path(log_path)}.lock")


def _generation_path(log_path):
    return Path(f"{Path(log_path)}.generation")


@contextmanager
def _log_lock(log_path, shared=False, timeout=None):
    """Coordinate all log reads, writes, and clears through one lock file."""
    lock_path = _lock_path(log_path)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        os.chmod(lock_path, 0o600)
        operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        if timeout is None:
            fcntl.flock(lock_file.fileno(), operation)
        else:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), operation | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out waiting for {lock_path}")
                    time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_generation(log_path):
    try:
        return int(_generation_path(log_path).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def _write_generation(log_path, generation):
    generation_path = _generation_path(log_path)
    generation_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{generation_path.name}.", dir=generation_path.parent
    )
    try:
        os.fchmod(fd, 0o600)
        payload = f"{generation}\n".encode("ascii")
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
        os.close(fd)
        os.replace(temporary_path, generation_path)
        os.chmod(generation_path, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def clear_log(log_path):
    """Clear the log atomically with writers and advance its generation.

    The generation is persisted before truncating the data file. Readers hold
    the same lock while observing both values, so a clear is an ordered
    boundary even when new records immediately make the file larger again.
    """
    log_path = Path(log_path)
    with _log_lock(log_path, timeout=1.0):
        generation = _read_generation(log_path)
        _write_generation(log_path, 0 if generation is None else generation + 1)
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.ftruncate(fd, 0)
            os.fsync(fd)
        finally:
            os.close(fd)


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
    with _log_lock(log_path):
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)


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
        self.generation = None
        self.file_identity = None

    def read_new(self, log_path):
        log_path = Path(log_path)
        with _log_lock(log_path, shared=True):
            generation = _read_generation(log_path)
            try:
                with log_path.open("rb") as log_file:
                    identity = (os.fstat(log_file.fileno()).st_dev,
                                os.fstat(log_file.fileno()).st_ino)
                    size = os.fstat(log_file.fileno()).st_size
                    restarted = (
                        self.file_identity is not None
                        and (identity != self.file_identity
                             or generation != self.generation
                             or size < self.offset)
                    )
                    if restarted:
                        self.offset = 0
                        self.pending = b""
                    log_file.seek(self.offset)
                    chunk = log_file.read()
            except FileNotFoundError:
                restarted = self.file_identity is not None or self.offset != 0 or bool(self.pending)
                self.offset = 0
                self.pending = b""
                self.file_identity = None
                self.generation = generation
                return [], restarted

            self.offset += len(chunk)
            self.file_identity = identity
            self.generation = generation
            records, self.pending = parse_complete_records(self.pending + chunk)
            return records, restarted


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("log_path")
    parser.add_argument("timestamp", type=int)
    parser.add_argument("event_type", choices=sorted(EVENT_TYPES))
    args = parser.parse_args(argv)
    write_event(args.log_path, args.timestamp, args.event_type, sys.stdin.read())


if __name__ == "__main__":
    main()
