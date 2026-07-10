#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

MANIFEST_DIR = Path(os.environ.get('AUTOMATION_MANIFEST_DIR', '/home/yk/physio-hermes-ops/dashboard/runtime/automation_job_manifests'))

KST = timezone(timedelta(hours=9))
JOBS_JSON = Path('/home/yk/.hermes/cron/jobs.json')
HERMES = '/home/yk/.local/bin/hermes'
POLL_SECONDS = 5
RUN_TIMEOUT_SECONDS = 240
JOBS = [
    ('pt_kpi', 'e98b2ed0910d', '월요일 09:00 PT KPI 요약'),
    ('zotero_ingest', 'df985f8b88e3', '월요일 09:00 Zotero 논문 수집'),
    ('zotero_git_sync', '531ac51ef721', '월요일 09:15 Zotero 결과 Git 동기화'),
]

JOB_ID = '43e36ea7bb36'
JOB_NAME = '월요일 09:00 주간 운영 패킷'


def write_manifest(started_at: datetime, lines: list[str], subjobs: list[dict], failures: int) -> None:
    finished_at = datetime.now(KST)
    payload = {
        'schemaVersion': 1,
        'evidenceSource': 'runtime-direct',
        'generatedAt': finished_at.isoformat(),
        'runStartedAt': started_at.isoformat(),
        'runFinishedAt': finished_at.isoformat(),
        'status': 'error' if failures else 'ok',
        'job': {'id': JOB_ID, 'name': JOB_NAME, 'runtime': 'hermes-script'},
        'createdFiles': [],
        'notionPages': [],
        'discordMessages': [],
        'artifacts': [],
        'errors': [item.get('detail') or item.get('name') or item.get('key') for item in subjobs if item.get('status') != 'ok'],
        'metadata': {
            'subjobs': subjobs,
            'subjobCount': len(subjobs),
            'failureCount': failures,
            'outputLines': lines,
        },
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f'{JOB_ID}.json'
    tmp_path = path.with_suffix('.json.tmp')
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp_path.replace(path)


def load_job(job_id: str) -> dict | None:
    jobs = json.loads(JOBS_JSON.read_text())['jobs']
    for job in jobs:
        if job.get('id') == job_id:
            return job
    return None


def terminate_process_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        try:
            proc.terminate()
        except Exception:
            return
    deadline = time.time() + 5
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.2)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def run_cron_job(job_id: str, name: str) -> tuple[bool, str]:
    before = load_job(job_id) or {}
    before_last_run = before.get('last_run_at')
    proc = subprocess.Popen(
        [HERMES, 'cron', 'run', job_id, '--now', '--accept-hooks'],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    started = time.time()
    completion_seen = False
    status_line = ''
    while time.time() - started < RUN_TIMEOUT_SECONDS:
        current = load_job(job_id) or {}
        last_run = current.get('last_run_at')
        last_status = current.get('last_status')
        last_error = current.get('last_error')
        if last_run and last_run != before_last_run and last_status in {'ok', 'error'}:
            completion_seen = True
            status_line = f'jobs.json completion detected: status={last_status} last_run_at={last_run} error={last_error}'
            break
        if proc.poll() is not None:
            break
        time.sleep(POLL_SECONDS)

    if completion_seen:
        terminate_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            stdout, stderr = '', ''
        output = ' '.join(part for part in [stdout.strip(), stderr.strip(), status_line] if part).strip()
        current = load_job(job_id) or {}
        return current.get('last_status') == 'ok', output

    if proc.poll() is None:
        terminate_process_group(proc)
        current = load_job(job_id) or {}
        if current.get('last_run_at') != before_last_run and current.get('last_status') in {'ok', 'error'}:
            output = f'timeout but status advanced: {current.get("last_status")} {current.get("last_run_at")} {current.get("last_error")}'
            return current.get('last_status') == 'ok', output
        return False, f'timed out waiting for {name}'

    try:
        stdout, stderr = proc.communicate(timeout=5)
    except Exception:
        stdout, stderr = '', ''
    output = '\n'.join(part for part in [stdout.strip(), stderr.strip()] if part).strip()
    current = load_job(job_id) or {}
    ok = proc.returncode == 0 and current.get('last_status') == 'ok'
    if current.get('last_run_at') != before_last_run:
        output = ' '.join(part for part in [output, f'status={current.get("last_status")}', f'last_run_at={current.get("last_run_at")}'] if part)
    return ok, output


def main() -> int:
    started_at = datetime.now(KST)
    stamp = started_at.strftime('%Y-%m-%d %H:%M:%S %Z')
    lines = [
        '[monday-weekly-ops-packet]',
        f'run_at: {stamp}',
    ]
    failures = 0
    for key, job_id, name in JOBS:
        ok, output = run_cron_job(job_id, name)
        status = 'ok' if ok else 'error'
        lines.append(f'{key}: {status} | {job_id} | {name}')
        compact = ' '.join(output.split()) if output else ''
        if output:
            lines.append(f'{key}_detail: {compact[:1400]}')
        subjobs.append({'key': key, 'jobId': job_id, 'name': name, 'status': status, 'detail': compact[:1400]})
        if not ok:
            failures += 1
            break
    write_manifest(started_at, lines, subjobs, failures)
    print('\n'.join(lines))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
