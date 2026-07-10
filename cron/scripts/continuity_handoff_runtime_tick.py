#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
import os
from pathlib import Path

CRON_JOB_ID = '6cd11d8bbd31'
CRON_OUTPUT_DIR = Path('/home/yk/.hermes/cron/output') / CRON_JOB_ID
SECOND_BRAIN_DIR = Path(os.environ.get('SECOND_BRAIN_DIR', '/home/yk/brain-linux'))
TARGET_DIR = SECOND_BRAIN_DIR / 'operations' / 'raw-handoff-digests'
NOTIFIER_SCRIPT = Path('/home/yk/.hermes/scripts/continuity_handoff_notifier.py')


def extract_markdown_block(text: str) -> str:
    match = re.search(r'## Response\s+```(?:markdown)?\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    marker = '## Response'
    idx = text.find(marker)
    if idx == -1:
        return ''
    return text[idx + len(marker):].strip()


def resolve_target_name(markdown: str, fallback_stem: str) -> str:
    match = re.search(r'^#\s+Raw Handoff Digest \((\d{4}-\d{2}-\d{2}-\d{4})\)', markdown, re.MULTILINE)
    if match:
        return f'{match.group(1)}.md'

    if '_' in fallback_stem:
        date_part, time_part = fallback_stem.split('_', 1)
        hhmm = time_part.replace('-', '')[:4]
        if len(hhmm) == 4:
            return f'{date_part}-{hhmm}.md'
    return f'{fallback_stem}.md'


def materialize_latest_handoff() -> str:
    if not CRON_OUTPUT_DIR.exists():
        return ''

    files = sorted(CRON_OUTPUT_DIR.glob('*.md'))
    if not files:
        return ''

    latest = files[-1]
    raw = latest.read_text(encoding='utf-8', errors='ignore')
    markdown = extract_markdown_block(raw)
    if not markdown:
        return ''

    target_name = resolve_target_name(markdown, latest.stem)
    target_path = TARGET_DIR / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)

    desired = markdown.rstrip() + '\n'
    existing = target_path.read_text(encoding='utf-8', errors='ignore') if target_path.exists() else None
    if existing == desired:
        return ''

    target_path.write_text(desired, encoding='utf-8')
    target_path.chmod(0o644)
    return f'[raw-handoff-materialized] {latest.name} -> {target_path}'


def run_notifier() -> str:
    if not NOTIFIER_SCRIPT.exists():
        return ''
    completed = subprocess.run(
        ['python3', str(NOTIFIER_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    chunks: list[str] = []
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        chunks.append(stdout)
    if completed.returncode != 0 and stderr:
        chunks.append(f'[continuity-handoff-notifier:error] {stderr}')
    return '\n'.join(chunks).strip()


def main() -> int:
    outputs: list[str] = []
    materialized = materialize_latest_handoff()
    if materialized:
        outputs.append(materialized)

    notifier = run_notifier()
    if notifier:
        outputs.append(notifier)

    if outputs:
        print('\n'.join(outputs))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
