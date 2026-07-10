#!/usr/bin/env python3
import subprocess
import sys

SCRIPT = '/home/yk/.hermes/skills/productivity/youngkwon-calendar-lightweight-ops/scripts/calendar_brief.py'
result = subprocess.run([
    'python', SCRIPT, '--day', 'today'
], capture_output=True, text=True)
if result.returncode != 0:
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)
print(result.stdout.strip())
