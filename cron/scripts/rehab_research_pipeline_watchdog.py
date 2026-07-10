#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.date().isoformat()
JOBS_PATH = Path('/home/yk/.hermes/cron/jobs.json')
OUTPUT_BASE = Path('/home/yk/.hermes/cron/output')

PIPELINE = {
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
    'second-brain-git-sync-batch': {
        'job_id': '291191b0acd7',
        'must_run_after': '06:35',
        'allowed_statuses': {'ok'},
    },
}


def load_jobs() -> dict:
    data = json.loads(JOBS_PATH.read_text())
    jobs = data.get('jobs', data) if isinstance(data, dict) else data
    normalized = {}
    for job in jobs:
        job_id = job.get('job_id') or job.get('id')
        if not job_id:
            continue
        normalized[job_id] = job
    return normalized


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def latest_output_text(job_id: str) -> str:
    out_dir = OUTPUT_BASE / job_id
    if not out_dir.exists():
        return ''
    files = sorted(out_dir.glob('*.md'))
    if not files:
        return ''
    return files[-1].read_text()


def has_missing_rehab_write_signals(text: str) -> list[str]:
    issues: list[str] = []
    if '## Response' not in text:
        issues.append('response section missing')
        return issues
    response = text.split('## Response', 1)[1]
    if 'Notion 적재 결과' not in response:
        issues.append('final response missing Notion section')
    if 'Now, I will prepare the JSON' in response:
        issues.append('response stopped at tool-intent text before actual write')
    if '/tmp/daily_rehab_brief_notion_' in response and 'Notion 적재 결과' not in response:
        issues.append('tmp JSON path mentioned without reported write result')
    return issues


def should_have_run(time_str: str) -> bool:
    hh, mm = map(int, time_str.split(':'))
    due = NOW.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return NOW >= due


def main() -> int:
    jobs = load_jobs()
    problems: list[str] = []

    for name, spec in PIPELINE.items():
        if not should_have_run(spec['must_run_after']):
            continue

        job = jobs.get(spec['job_id'])
        if not job:
            problems.append(f'- {name}: jobs.json에서 잡을 찾지 못함')
            continue

        last_status = job.get('last_status')
        last_run_at = parse_iso(job.get('last_run_at'))
        state = job.get('state')
        enabled = job.get('enabled')

        if not enabled or state == 'paused':
            problems.append(f'- {name}: paused/disabled 상태')
            continue

        if last_status not in spec['allowed_statuses']:
            problems.append(f'- {name}: last_status={last_status!r}')
            continue

        if last_run_at is None or last_run_at.astimezone(KST).date().isoformat() != TODAY:
            problems.append(f'- {name}: 오늘 실행 기록 없음 (last_run_at={job.get("last_run_at")})')
            continue

        text = latest_output_text(spec['job_id'])

        if name == 'daily-rehab-ai-research-brief':
            for issue in has_missing_rehab_write_signals(text):
                problems.append(f'- {name}: {issue}')

        if name == 'second-brain-git-sync-batch':
            if TODAY not in text:
                problems.append(f'- {name}: 오늘 output 파일 확인 실패')
            elif 'status: pushed' not in text and 'status: no changes' not in text:
                m = re.search(r'status:\s*(.+)', text)
                status_line = m.group(1).strip() if m else 'unknown'
                problems.append(f'- {name}: output status={status_line}')

    if not problems:
        return 0

    print('[rehab research pipeline watchdog]')
    print(f'date: {TODAY}')
    print('status: attention-needed')
    print('impact: 재활 리서치 브리핑→Notion export→second-brain sync 파이프라인 중 일부가 오늘 정상 완료되지 않았을 수 있음')
    print('suggest: 아래 이슈 확인 후 해당 잡 재실행 또는 원인 보정 권장')
    print('issues:')
    for item in problems:
        print(item)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
