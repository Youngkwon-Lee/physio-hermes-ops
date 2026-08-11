#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
ROOT = Path('/home/yk/physio-hermes-ops')
BRAIN = Path('/home/yk/brain-linux')
JOBS_JSON = Path('/home/yk/.hermes/cron/jobs.json')
MANIFEST_DIR = Path(os.environ.get('AUTOMATION_MANIFEST_DIR', str(ROOT / 'dashboard/runtime/automation_job_manifests')))
JOB_ID = 'a05100ef81ac'
JOB_NAME = '매일 22:00 디스코드 nightly 패킷'
WINDOW = timedelta(hours=24)


def parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)


def read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default


def recent_files(root: Path, age: timedelta, pattern: str = '*') -> list[Path]:
    cutoff = NOW - age
    try:
        return [item for item in root.glob(pattern) if item.is_file() and datetime.fromtimestamp(item.stat().st_mtime, KST) >= cutoff]
    except OSError:
        return []


def dated_files(root: Path, first_day: date, last_day: date, pattern: str = '*.md') -> list[Path]:
    result: list[Path] = []
    try:
        for item in root.glob(pattern):
            if not item.is_file():
                continue
            match = re.search(r'(20\d{2}-\d{2}-\d{2})', item.name)
            if not match:
                continue
            try:
                item_day = date.fromisoformat(match.group(1))
            except ValueError:
                continue
            if first_day <= item_day <= last_day:
                result.append(item)
    except OSError:
        return []
    return result


def load_jobs() -> list[dict]:
    payload = read_json(JOBS_JSON, {})
    return payload.get('jobs', []) if isinstance(payload, dict) else []


def job_snapshot() -> tuple[dict, list[str]]:
    jobs = load_jobs()
    recent = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        last_run = parse_dt(job.get('last_run_at'))
        if last_run and last_run >= NOW - WINDOW:
            recent.append(job)
    counts = {'ok': 0, 'error': 0, 'paused': 0, 'other': 0}
    errors: list[str] = []
    for job in recent:
        status = job.get('last_status') if job.get('enabled', True) else 'paused'
        bucket = status if status in {'ok', 'error'} else 'other'
        counts[bucket] += 1
        if status == 'error':
            errors.append(f"{job.get('name', job.get('id', 'unknown'))}: {job.get('last_error') or 'error'}")
    return {'total': len(recent), **counts}, errors[:5]


def manifest_snapshot() -> tuple[dict, list[str]]:
    files = recent_files(MANIFEST_DIR, WINDOW, '*.json')
    counts = {'total': 0, 'ok': 0, 'error': 0, 'other': 0}
    errors: list[str] = []
    for path in files:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        counts['total'] += 1
        status = payload.get('status')
        if status in {'ok', 'error'}:
            counts[status] += 1
        else:
            counts['other'] += 1
        if status == 'error':
            details = payload.get('errors') or []
            detail = details[0] if isinstance(details, list) and details else 'error'
            errors.append(f'{path.stem}: {detail}')
    return counts, errors[:5]


def write_manifest(started_at: datetime, lines: list[str], metadata: dict) -> None:
    finished_at = datetime.now(KST)
    payload = {
        'schemaVersion': 1,
        'evidenceSource': 'runtime-direct',
        'generatedAt': finished_at.isoformat(),
        'runStartedAt': started_at.isoformat(),
        'runFinishedAt': finished_at.isoformat(),
        'status': 'ok',
        'job': {'id': JOB_ID, 'name': JOB_NAME, 'runtime': 'hermes-script'},
        'createdFiles': [],
        'artifacts': [],
        'discordMessages': [],
        'errors': [],
        'metadata': {**metadata, 'outputLines': lines, 'deliveryMode': 'local', 'duplicateSendPrevented': True},
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f'{JOB_ID}.json'
    tmp_path = path.with_suffix('.json.tmp')
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp_path.replace(path)


def main() -> int:
    started_at = datetime.now(KST)
    jobs, job_errors = job_snapshot()
    manifests, manifest_errors = manifest_snapshot()
    candidates = dated_files(BRAIN / 'candidates', NOW.date(), NOW.date())
    sync_job = next((job for job in load_jobs() if job.get('name') == '30분마다 second-brain Git 동기화 묶음'), None)
    sync_status = sync_job.get('last_status', 'unknown') if sync_job else 'not found'
    errors = job_errors + manifest_errors
    lines = [
        '[daily-discord-nightly-packet]',
        f'run_at: {started_at.strftime("%Y-%m-%d %H:%M:%S %Z")}',
        'mode: direct snapshot; paused legacy child jobs were not executed',
        f'cron jobs (24h): total={jobs["total"]}, ok={jobs["ok"]}, error={jobs["error"]}, paused-or-other={jobs["other"]}',
        f'automation manifests (24h): total={manifests["total"]}, ok={manifests["ok"]}, error={manifests["error"]}',
        f'second-brain candidates (24h): {len(candidates)}',
        f'second-brain sync latest status: {sync_status}',
        f'notable errors: {"; ".join(errors) if errors else "none"}',
        'delivery: local only; no direct Discord send from this packet',
    ]
    write_manifest(started_at, lines, {
        'windowHours': 24,
        'cronJobs': jobs,
        'automationManifests': manifests,
        'candidateCount': len(candidates),
        'secondBrainSyncStatus': sync_status,
        'legacyChildrenExecuted': False,
    })
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
