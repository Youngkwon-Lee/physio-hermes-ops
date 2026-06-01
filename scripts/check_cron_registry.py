#!/usr/bin/env python3
"""Compare public-safe cron registry against live Hermes cron state.

Checks:
- missing/extra jobs by name
- schedule mismatch
- mode mismatch (agent vs script)
- toolset mismatch for agent jobs
- tracked prompt/script file existence inside the repo

Usage:
  python scripts/check_cron_registry.py
  python scripts/check_cron_registry.py --strict
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "cron" / "registry" / "jobs.yaml"


def load_registry() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    return {job["name"]: job for job in jobs if isinstance(job, dict) and job.get("name")}


def parse_live_jobs(text: str) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        header = re.match(r"\s*([0-9a-f]{12})\s+\[([^\]]+)\]\s*$", line)
        if header:
            current = {
                "job_id": header.group(1),
                "state_tag": header.group(2),
                "mode": "agent",
                "enabled_toolsets": [],
            }
            continue
        if current is None:
            continue
        field = re.match(r"\s+(Name|Schedule|Deliver|Script|Mode|Skills):\s+(.*)$", line)
        if not field:
            continue
        key, value = field.group(1), field.group(2).strip()
        if key == "Name":
            current["name"] = value
            jobs[value] = current
        elif key == "Schedule":
            current["schedule"] = value
        elif key == "Deliver":
            current["deliver"] = value
        elif key == "Script":
            current["script"] = value
            current["mode"] = "script"
        elif key == "Mode":
            if "no-agent" in value:
                current["mode"] = "script"
        elif key == "Skills":
            current["skills"] = [item.strip() for item in value.split(",") if item.strip()]
    return jobs


def get_live_jobs() -> dict[str, dict[str, Any]]:
    proc = subprocess.run(["hermes", "cron", "list", "--all"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "hermes cron list failed")
    return parse_live_jobs(proc.stdout)


def compare(registry: dict[str, dict[str, Any]], live: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    registry_names = set(registry)
    live_names = set(live)

    for name in sorted(registry_names - live_names):
        issues.append({"severity": "error", "job": name, "issue": "missing_live_job"})
    for name in sorted(live_names - registry_names):
        issues.append({"severity": "warn", "job": name, "issue": "untracked_live_job"})

    for name in sorted(registry_names & live_names):
        reg = registry[name]
        runtime = live[name]

        if reg.get("schedule") != runtime.get("schedule"):
            issues.append({
                "severity": "error",
                "job": name,
                "issue": "schedule_mismatch",
                "registry": str(reg.get("schedule")),
                "live": str(runtime.get("schedule")),
            })

        reg_mode = reg.get("mode")
        live_mode = runtime.get("mode", "agent")
        if reg_mode != live_mode:
            issues.append({
                "severity": "error",
                "job": name,
                "issue": "mode_mismatch",
                "registry": str(reg_mode),
                "live": str(live_mode),
            })

        if reg_mode == "script":
            script_file = reg.get("script_file")
            if not script_file:
                issues.append({"severity": "error", "job": name, "issue": "missing_script_file_field"})
            else:
                full_path = ROOT / script_file
                if not full_path.exists():
                    issues.append({
                        "severity": "error",
                        "job": name,
                        "issue": "missing_repo_script_file",
                        "path": script_file,
                    })
                live_script = runtime.get("script")
                if live_script and Path(script_file).name != Path(live_script).name:
                    issues.append({
                        "severity": "warn",
                        "job": name,
                        "issue": "script_basename_mismatch",
                        "registry": Path(script_file).name,
                        "live": str(live_script),
                    })
        else:
            prompt_file = reg.get("prompt_file")
            if not prompt_file:
                issues.append({"severity": "error", "job": name, "issue": "missing_prompt_file_field"})
            else:
                full_path = ROOT / prompt_file
                if not full_path.exists():
                    issues.append({
                        "severity": "error",
                        "job": name,
                        "issue": "missing_repo_prompt_file",
                        "path": prompt_file,
                    })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    args = parser.parse_args()

    registry = load_registry()
    live = get_live_jobs()
    issues = compare(registry, live)

    summary = {
        "registry_jobs": len(registry),
        "live_jobs": len(live),
        "errors": sum(1 for item in issues if item["severity"] == "error"),
        "warnings": sum(1 for item in issues if item["severity"] == "warn"),
        "issues": issues,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["errors"]:
        return 1
    if args.strict and summary["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
