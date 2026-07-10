#!/usr/bin/env python3
import subprocess
import sys

cmd = [
    'python3',
    '/home/yk/.hermes/skills/productivity/google-workspace/scripts/setup.py',
    '--check',
]
proc = subprocess.run(cmd, capture_output=True, text=True)
out = (proc.stdout or '').strip()
err = (proc.stderr or '').strip()
combined = '\n'.join([x for x in [out, err] if x]).strip()

# Stay silent when healthy. Notify only on broken/auth-warning states.
if proc.returncode == 0 and 'AUTHENTICATED' in combined and 'partial' not in combined.lower():
    sys.exit(0)

print('# Google token watchdog alert')
print('- check command: python /home/yk/.hermes/skills/productivity/google-workspace/scripts/setup.py --check')
print('- status: attention needed')
print('')
print('```')
print(combined or '(no output)')
print('```')
