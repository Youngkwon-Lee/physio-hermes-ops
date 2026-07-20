#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "cron" / "registry" / "jobs.yaml"
DEFAULT_JOBS_JSON = Path("/home/yk/.hermes/cron/jobs.json")
KST = timezone(timedelta(hours=9))


def load_registry(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    return [job for job in jobs if isinstance(job, dict) and job.get("prompt_file")]


def live_names(job: dict[str, Any]) -> set[str]:
    names = {str(job.get("name") or "").strip()}
    runtime_name = str(job.get("runtime_name") or "").strip()
    if runtime_name:
        names.add(runtime_name)
    aliases = job.get("runtime_aliases") or []
    if isinstance(aliases, list):
        names.update(str(alias).strip() for alias in aliases if str(alias).strip())
    return {name for name in names if name}


def live_job_key(job: dict[str, Any]) -> str:
    return str(job.get("id") or job.get("job_id") or job.get("name") or "")


def selected(job: dict[str, Any], live: dict[str, Any] | None, selectors: set[str]) -> bool:
    if not selectors:
        return True
    candidates = live_names(job)
    if live is not None:
        candidates.add(live_job_key(live))
    return bool(candidates & selectors)


def find_live_job(registry_job: dict[str, Any], live_jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = live_names(registry_job)
    for live in live_jobs:
        if live.get("name") in candidates or live_job_key(live) in candidates:
            return live
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync versioned cron prompt files into live Hermes jobs.json.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--jobs-json", type=Path, default=DEFAULT_JOBS_JSON)
    parser.add_argument("--job", action="append", default=[], help="Registry name, runtime name, or live job id to sync.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    registry_jobs = load_registry(args.registry)
    selectors = set(args.job)
    live_payload = json.loads(args.jobs_json.read_text(encoding="utf-8"))
    live_jobs = live_payload.get("jobs", live_payload if isinstance(live_payload, list) else [])

    updates: list[dict[str, Any]] = []
    missing: list[str] = []
    for registry_job in registry_jobs:
        prompt_path = ROOT / str(registry_job["prompt_file"])
        if not prompt_path.exists():
            missing.append(f"{registry_job['name']}: missing prompt file {registry_job['prompt_file']}")
            continue
        live = find_live_job(registry_job, live_jobs)
        if not selected(registry_job, live, selectors):
            continue
        if live is None:
            missing.append(f"{registry_job['name']}: missing live job")
            continue
        prompt = prompt_path.read_text(encoding="utf-8")
        changed = live.get("prompt") != prompt
        updates.append({
            "registryName": registry_job["name"],
            "liveName": live.get("name"),
            "liveId": live_job_key(live),
            "promptFile": str(registry_job["prompt_file"]),
            "changed": changed,
        })
        if changed and not args.dry_run:
            live["prompt"] = prompt

    if missing:
        print(json.dumps({"status": "blocked", "updates": updates, "missing": missing}, ensure_ascii=False, indent=2))
        return 1

    if not args.dry_run and any(item["changed"] for item in updates):
        if not args.no_backup:
            suffix = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
            backup = args.jobs_json.with_name(f"{args.jobs_json.name}.bak-prompt-sync-{suffix}")
            shutil.copy2(args.jobs_json, backup)
        args.jobs_json.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "dryRun": args.dry_run, "updates": updates}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
