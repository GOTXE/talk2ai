"""Regression coverage for bounded cancellation of an AI turn."""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DAEMON = REPO / "scripts" / "talk2ai-daemon"


class DaemonCancellationTest(unittest.TestCase):
    def _read_driver(self, emitted, cancel_after=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver = root / "driver.sh"
            driver.write_text("#!/bin/bash\n" + emitted)
            driver.chmod(0o755)
            harness = r'''
source "$DAEMON"
set -u
temporary=$(mktemp -d)
: > "$temporary/.talk2ai-turn"
fifo="$temporary/driver.fifo"
pid_file="$temporary/driver.pid"
mkfifo "$fifo"
setsid "$DRIVER" >"$fifo" &
monitor=$!
printf '%s\n' "$monitor" > "$pid_file"
exec {_driver_fd}<"$fifo"
rm -f "$fifo"
response=""
started=$(date +%s%3N)
while :; do
    _read_driver_char
    status=$?
    [ -n "$_driver_char" ] && [ "$_driver_char" != $'\n' ] && response+="$_driver_char"
    if [ "$status" -eq 2 ]; then
        if [ -n "${CANCEL_AFTER:-}" ] && [ $(( $(date +%s%3N) - started )) -ge "$CANCEL_AFTER" ]; then
            _stop_turn_driver "$pid_file" "$monitor"
            break
        fi
        kill -0 "$monitor" 2>/dev/null || break
    elif [ "$status" -eq 1 ]; then
        break
    elif [ "$status" -ne 0 ]; then
        exit 2
    fi
done
exec {_driver_fd}<&-
_cleanup_turn_driver "$temporary"
[ -e "$temporary" ] && exit 3
printf '%s' "$response"
'''
            env = {**os.environ, "DAEMON": str(DAEMON), "DRIVER": str(driver)}
            if cancel_after is not None:
                env["CANCEL_AFTER"] = str(cancel_after)
            result = subprocess.run(["bash", "-c", harness], env=env,
                                    text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def test_incremental_reader_preserves_pauses_tokens_unicode_and_final_line(self):
        cases = [
            ("printf 'Hola '; sleep 0.4; printf 'mundo\\n'", "Hola mundo"),
            ("printf 'H'; sleep 0.1; printf 'o'; sleep 0.5; printf 'la mundo\\n'", "Hola mundo"),
            ("printf 'Respuesta sin salto final'", "Respuesta sin salto final"),
            ("printf '¿Qué tal, ñandú? ¡Muy bien!\\n'", "¿Qué tal, ñandú? ¡Muy bien!"),
            ("printf 'fragmento '; sleep 0.2; printf 'largo '; sleep 0.4; printf 'con pausas '; sleep 0.1; printf 'irregulares\\n'", "fragmento largo con pausas irregulares"),
        ]
        for emitted, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self._read_driver(emitted), expected)

    def test_incremental_reader_cancel_discards_only_the_current_turn(self):
        result = self._read_driver(
            "printf 'cancelación parcial '; sleep 2; printf 'que no debe llegar\\n'",
            cancel_after=250,
        )
        self.assertEqual(result, "cancelación parcial ")

    def test_blocked_driver_is_terminated_without_waiting_for_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            driver = state / "ia" / "blocked"
            driver.parent.mkdir(parents=True)
            driver.write_text("#!/bin/bash\nsleep 30\n")
            driver.chmod(0o755)
            harness = r'''
source "$DAEMON"
TALK2AI_DIR="$STATE"
DRIVER_FILE="$STATE/driver"
MODEL_FILE="$STATE/model"
_err_tmp=$(mktemp)
_driver_pid_file=$(mktemp)
printf 'blocked\n' > "$DRIVER_FILE"
_driver_tmp_dir=$(mktemp -d)
chmod 700 "$_driver_tmp_dir"
: > "$_driver_tmp_dir/.talk2ai-turn"
_driver_fifo="$_driver_tmp_dir/driver.fifo"
mkfifo "$_driver_fifo"
_run_driver 'silencio' >"$_driver_fifo" &
_driver_monitor_pid=$!
exec {_driver_fd}<"$_driver_fifo"
rm -f "$_driver_fifo"
started=$(date +%s%3N)
sleep 0.2
_stop_turn_driver "$_driver_pid_file" "$_driver_monitor_pid"
_stop_turn_driver "$_driver_pid_file" "$_driver_monitor_pid"
elapsed=$(( $(date +%s%3N) - started ))
exec {_driver_fd}<&-
_cleanup_turn_driver "$_driver_tmp_dir"
printf '%s\n' "$elapsed"
'''
            env = {**os.environ, "DAEMON": str(DAEMON), "STATE": str(state)}
            started = time.monotonic()
            result = subprocess.run(
                ["bash", "-c", harness], env=env, text=True,
                capture_output=True, timeout=4,
            )
            elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(elapsed, 3)
            self.assertLess(int(result.stdout.strip()), 2500)


if __name__ == "__main__":
    unittest.main()
