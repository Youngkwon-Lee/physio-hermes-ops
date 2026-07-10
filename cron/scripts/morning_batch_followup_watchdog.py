#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.date().isoformat()
WEEKDAY = NOW.weekday()  # Mon=0
JOBS_PATH = Path('/home/yk/.hermes/cron/jobs.json')
OUTPUT_BASE = Path('/home/yk/.hermes/cron/output')

CHECKS = {
    'daily-rehab-ai-research-brief': {
        'job_id': 'daeb6079f4f0',
        'must_run_after': '06:00',
        'allowed_statuses': {'ok'},
    },
    'notion-brain-candidate-exporter': {
        'job_id': '202384ffa9d3',
        'must_run_after': '06:20',
        'allowed_statuses': {'ok'},
    },
    'second-brain-candidate-git-sync': {
        'job_id': '65a6f6edc9d0',
        'must_run_after': '06:35',
        'allowed_statuses': {'ok'},
    },
    'rehab-research-pipeline-watchdog': {
        'job_id': '9ff452874c27',
        'must_run_after': '06:50',
        'allowed_statuses': {'ok'},
    },
    'daily-calendar-mail-brief': {
        'job_id': 'c6189af77c58',
        'must_run_after': '07:30',
        'allowed_statuses': {'ok'},
        'weekdays_only': True,
    },
    'daily-ai-news-discussion-kickoff': {
        'job_id': '09353aa4649f',
        'must_run_after': '07:30',
        'allowed_statuses': {'ok'},
    },
    'home-rehab-morning-brief': {
        'job_id': 'aaf858a79e67',
        'must_run_after': '07:45',
        'allowed_statuses': {'ok'},
    },
    'home-rehab-lunch-recommendation': {
        'job_id': 'f78f94ef7be3',
        'must_run_after': '08:00',
        'allowed_statuses': {'ok'},
    },
}


def load_jobs() -> dict[str, dict]:
    data = json.loads(JOBS_PATH.read_text())
    jobs = data.get('jobs', data) if isinstance(data, dict) else data
    normalized: dict[str, dict] = {}
    for job in jobs:
        job_id = job.get('job_id') or job.get('id')
        if job_id:
            normalized[job_id] = job
    return normalized


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def should_check(spec: dict) -> bool:
    if spec.get('weekdays_only') and WEEKDAY >= 5:
        return False
    hh, mm = map(int, spec['must_run_after'].split(':'))
    due = NOW.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return NOW >= due


def latest_output_text(job_id: str) -> str:
    out_dir = OUTPUT_BASE / job_id
    if not out_dir.exists():
        return ''
    files = sorted(out_dir.glob('*.md'))
    if not files:
        return ''
    return files[-1].read_text()


def output_status(text: str) -> str:
    m = re.search(r'status:\s*(.+)', text)
    return m.group(1).strip() if m else 'unknown'


def main() -> int:
    jobs = load_jobs()
    problems: list[str] = []
    checked: list[str] = []

    for name, spec in CHECKS.items():
        if not should_check(spec):
            continue

        checked.append(name)
        job = jobs.get(spec['job_id'])
        if not job:
            problems.append(f'- {name}: jobs.json에서 잡을 찾지 못함')
            continue

        if not job.get('enabled') or job.get('state') == 'paused':
            problems.append(f'- {name}: paused/disabled 상태')
            continue

        last_status = job.get('last_status')
        if last_status not in spec['allowed_statuses']:
            problems.append(f'- {name}: last_status={last_status!r}')
            continue

        last_run_at = parse_iso(job.get('last_run_at'))
        if last_run_at is None or last_run_at.astimezone(KST).date().isoformat() != TODAY:
            problems.append(f'- {name}: 오늘 실행 기록 없음 (last_run_at={job.get("last_run_at")})')
            continue

        if name == 'second-brain-candidate-git-sync':
            text = latest_output_text(spec['job_id'])
            status = output_status(text)
            if TODAY not in text:
                problems.append(f'- {name}: 오늘 output 파일 확인 실패')
            elif status not in {'pushed', 'no changes'}:
                problems.append(f'- {name}: output status={status}')

        if name == 'rehab-research-pipeline-watchdog':
            text = latest_output_text(spec['job_id'])
            status = output_status(text)
            if TODAY not in text:
                problems.append(f'- {name}: 오늘 output 파일 확인 실패')
            elif status != 'ok':
                problems.append(f'- {name}: output status={status}')

    print('[morning batch followup watchdog]')
    print(f'date: {TODAY}')
    print(f'checked_count: {len(checked)}')

    if not problems:
        print('status: ok')
        print('checked: ' + ', '.join(checked))
        return 0

    print('status: attention-needed')
    print('issues:')
    for item in problems:
        print(item)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
