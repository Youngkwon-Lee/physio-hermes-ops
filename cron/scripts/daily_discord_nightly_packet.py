#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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
RUN_TIMEOUT_SECONDS = 180
JOBS = [
    ('action_staging', '01dd14f9c228', '매일 23:25 디스코드 액션 정리', 'cron'),
    ('daily_digest', '851efbda287e', '매일 23:50 디스코드 하루 요약', 'cron'),
    ('postsync', 'f5ace0662536', '매일 23:55 디스코드 요약 후처리', 'script'),
]

JOB_ID = 'a05100ef81ac'
JOB_NAME = '매일 23:25 디스코드 nightly 패킷'


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


def run_script_job(name: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ['python3', '/home/yk/.hermes/scripts/daily_discord_digest_postsync.py'],
        text=True,
        capture_output=True,
        timeout=180,
    )
    output = '\n'.join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
    return proc.returncode == 0, output or f'{name} returned {proc.returncode}'


def compact_detail(output: str) -> str:
    text = ' '.join(output.split()) if output else ''
    if not text:
        return ''
    text = re.sub(r'Output saved to:\s+\S+', 'output saved', text)
    text = re.sub(r'source:\s+\S+', 'source: saved digest', text)
    text = re.sub(r'candidate:\s+\S+', 'candidate: saved', text)
    text = re.sub(r'commit:\s+[0-9a-f]{7,40}', 'commit: pushed', text)
    text = re.sub(r'notion_db_id:\s+\S+', 'notion_db_id: present', text)
    text = re.sub(r'notion_data_source_id:\s+\S+', 'notion_data_source_id: present', text)
    text = re.sub(r'longterm_memory_db_id:\s+\S+', 'longterm_memory_db_id: present', text)
    text = re.sub(r'longterm_memory_data_source_id:\s+\S+', 'longterm_memory_data_source_id: present', text)
    return text[:900]


def main() -> int:
    started_at = datetime.now(KST)
    stamp = started_at.strftime('%Y-%m-%d %H:%M:%S %Z')
    lines = [
        '[daily-discord-nightly-packet]',
        f'run_at: {stamp}',
        'mode: wrapper invokes paused legacy digest jobs to avoid duplicate direct schedules',
    ]
    failures = 0
    subjobs: list[dict] = []
    for key, job_id, name, mode in JOBS:
        if mode == 'cron':
            ok, output = run_cron_job(job_id, name)
        else:
            ok, output = run_script_job(name)
        status = 'ok' if ok else 'error'
        lines.append(f'{key}: {status} | {job_id} | {name}')
        compact = compact_detail(output)
        if compact:
            lines.append(f'{key}_detail: {compact[:1400]}')
        subjobs.append({'key': key, 'jobId': job_id, 'name': name, 'mode': mode, 'status': status, 'detail': compact[:1400]})
        if not ok:
            failures += 1
            break
    write_manifest(started_at, lines, subjobs, failures)
    print('\n'.join(lines))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
