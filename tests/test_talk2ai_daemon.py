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
_driver_fifo=$(mktemp -u)
mkfifo "$_driver_fifo"
_run_driver 'silencio' >"$_driver_fifo" &
_driver_monitor_pid=$!
exec {_driver_fd}<"$_driver_fifo"
rm -f "$_driver_fifo"
started=$(date +%s%3N)
sleep 0.2
_stop_turn_driver "$_driver_pid_file" "$_driver_monitor_pid"
elapsed=$(( $(date +%s%3N) - started ))
exec {_driver_fd}<&-
rm -f "$_err_tmp" "$_driver_pid_file"
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
