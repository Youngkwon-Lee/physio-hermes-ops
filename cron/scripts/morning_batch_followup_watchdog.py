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
MANIFEST_BASE = Path('/home/yk/physio-hermes-ops/dashboard/runtime/automation_job_manifests')

CHECKS = {
    'daily-rehab-ai-research-brief': {
        'job_id': 'daeb6079f4f0',
        'must_run_after': '06:00',
        'allowed_statuses': {'ok'},
        'manifest_required': True,
    },
    'notion-brain-candidate-exporter': {
        'job_id': '202384ffa9d3',
        'must_run_after': '06:20',
        'allowed_statuses': {'ok'},
        'output_must_include_today': True,
    },
    'rehab-research-notion-backfill-watchdog': {
        'job_id': 'b4564dfeee23',
        'must_run_after': '06:40',
        'allowed_statuses': {'ok'},
        'output_must_include_today': True,
    },
    'morning-operating-brief': {
        'job_id': 'e4f4c4661364',
        'must_run_after': '06:45',
        'allowed_statuses': {'ok'},
        'manifest_required': True,
        'weekdays_only': True,
    },
    'second-brain-git-sync-batch': {
        'job_id': '291191b0acd7',
        'must_run_after': '07:00',
        'allowed_statuses': {'ok'},
        'output_must_include_today': True,
        'output_status_allow': {'ok'},
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


def load_manifest(job_id: str) -> dict | None:
    path = MANIFEST_BASE / f'{job_id}.json'
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def manifest_date(manifest: dict, job_id: str) -> str | None:
    for key in ('runFinishedAt', 'generatedAt', 'createdAt'):
        parsed = parse_iso(manifest.get(key))
        if parsed is not None:
            return parsed.astimezone(KST).date().isoformat()

    path = MANIFEST_BASE / f'{job_id}.json'
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, KST).date().isoformat()
    return None


def manifest_is_ok(manifest: dict) -> bool:
    if manifest.get('status') in {'ok', 'success'}:
        return True
    if manifest.get('status') in {'failed', 'error'}:
        return False
    errors = manifest.get('errors')
    return isinstance(errors, list) and len(errors) == 0


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

        if spec.get('manifest_required'):
            manifest = load_manifest(spec['job_id'])
            if manifest is None:
                problems.append(f'- {name}: manifest 파일 없음')
                continue
            if manifest_date(manifest, spec['job_id']) != TODAY:
                problems.append(f'- {name}: manifest 날짜가 오늘이 아님')
                continue
            if not manifest_is_ok(manifest):
                problems.append(f'- {name}: manifest status={manifest.get("status")!r}')
                continue

        text = latest_output_text(spec['job_id'])
        if spec.get('output_must_include_today'):
            if TODAY not in text:
                problems.append(f'- {name}: 오늘 output 파일 확인 실패')
                continue

        if name == 'second-brain-git-sync-batch':
            text = latest_output_text(spec['job_id'])
            status = output_status(text)
            if status not in spec.get('output_status_allow', set()):
                problems.append(f'- {name}: output status={status}')

    if not problems:
        print('아침 브리프 후속 확인')
        print('- 상태: 정상')
        print(f'- 확인: {len(checked)}개 파이프라인')
        print('- 조치: 없음')
        return 0

    print('아침 브리프 후속 확인')
    print('- 상태: 확인 필요')
    print(f'- 확인: {len(checked)}개 파이프라인')
    print(f'- 문제: {len(problems)}개')
    print('- 조치: Kinelo Ops /system/automation에서 해당 잡의 최근 실행과 manifest를 확인')
    print('- 항목:')
    for item in problems:
        print(f'  {item}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
