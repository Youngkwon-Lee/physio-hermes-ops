#!/usr/bin/env python3
"""Delegate the home-desktop watchdog to the canonical second-brain sync script.

The canonical script lives in brain-linux so Windows, macOS, and the home
desktop share one reconciliation policy. This wrapper remains the Hermes
watchdog entrypoint and preserves its stdout/exit status.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


TARGET = Path(
    os.environ.get(
        "SECOND_BRAIN_AUTO_SYNC_SCRIPT",
        "/home/yk/brain-linux/operations/tools/second_brain_auto_sync.py",
    )
).expanduser()


def main() -> int:
    if not TARGET.is_file():
        print(f"[Second Brain Safe Sync]\nstatus: blocked\nreason: missing canonical script: {TARGET}")
        return 1

    result = subprocess.run(
        [sys.executable, str(TARGET)],
        cwd=TARGET.parents[2],
        text=True,
        capture_output=True,
    )
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
