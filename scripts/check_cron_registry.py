#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ENV = "HERMES_CRON_PROFILE"


def load_registry() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((ROOT / "cron" / "registry" / "jobs.yaml").read_text(encoding="utf-8"))
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


def registry_live_names(job: dict[str, Any]) -> list[str]:
    names = [str(job.get("name") or "").strip()]
    runtime_name = str(job.get("runtime_name") or "").strip()
    if runtime_name:
        names.append(runtime_name)
    runtime_aliases = job.get("runtime_aliases") or []
    if isinstance(runtime_aliases, list):
        names.extend(str(alias).strip() for alias in runtime_aliases)
    return [name for name in dict.fromkeys(names) if name]


def registry_candidate_names(registry: dict[str, dict[str, Any]]) -> set[str]:
    return {name for job in registry.values() for name in registry_live_names(job)}


def runtime_only_job_names(registry: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(name for name, job in registry.items() if job.get("source_state") == "runtime_only")


def find_live_job(
    registry_job: dict[str, Any],
    live: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    for name in registry_live_names(registry_job):
        if name in live:
            return name, live[name]
    return None, None


def hermes_executable() -> str:
    configured = os.getenv("HERMES_BIN", "").strip()
    if configured:
        return configured
    found = shutil.which("hermes")
    if found:
        return found
    user_bin = Path.home() / ".local" / "bin" / "hermes"
    if user_bin.exists():
        return str(user_bin)
    return "hermes"


def hermes_cron_command(profile: str | None) -> list[str]:
    command = [hermes_executable()]
    if profile:
        command.extend(["-p", profile])
    command.extend(["cron", "list", "--all"])
    return command


def get_live_jobs(profile: str | None) -> dict[str, dict[str, Any]]:
    command = hermes_cron_command(profile)
    try:
        proc = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Hermes executable not found: {command[0]}") from exc
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "hermes cron list failed")
    return parse_live_jobs(proc.stdout)


def live_environment_issue(
    registry: dict[str, dict[str, Any]],
    live: dict[str, dict[str, Any]],
    profile: str | None,
) -> dict[str, str] | None:
    if not registry:
        return None
    if not live:
        return {
            "kind": "no_live_jobs",
            "profile": profile or "default",
            "message": (
                "Hermes returned no cron jobs. Verify --profile or "
                f"{PROFILE_ENV} points at the desktop Hermes runtime."
            ),
        }
    if registry_candidate_names(registry).isdisjoint(live):
        return {
            "kind": "no_registry_job_overlap",
            "profile": profile or "default",
            "message": (
                "Live Hermes cron jobs do not overlap the registry. "
                "This is probably the wrong Hermes profile for this repo."
            ),
        }
    return None


def compare(registry: dict[str, dict[str, Any]], live: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    live_names = set(live)
    matched_live_names: set[str] = set()

    for name in sorted(registry):
        reg = registry[name]
        runtime_only = reg.get("source_state") == "runtime_only"
        live_name, runtime = find_live_job(reg, live)
        if runtime is None:
            issues.append({"severity": "error", "job": name, "issue": "missing_live_job"})
            continue
        if live_name:
            matched_live_names.add(live_name)

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
            script_name = script_file or reg.get("runtime_script")
            if not script_file and not runtime_only:
                issues.append({"severity": "error", "job": name, "issue": "missing_script_file_field"})
            elif script_file:
                full_path = ROOT / script_file
                if not full_path.exists():
                    issues.append({
                        "severity": "error",
                        "job": name,
                        "issue": "missing_repo_script_file",
                        "path": script_file,
                    })
            live_script = runtime.get("script")
            if live_script and script_name and Path(script_name).name != Path(live_script).name:
                issues.append({
                    "severity": "warn",
                    "job": name,
                    "issue": "script_basename_mismatch",
                    "registry": Path(script_name).name,
                    "live": str(live_script),
                })
        else:
            prompt_file = reg.get("prompt_file")
            if not prompt_file and not runtime_only:
                issues.append({"severity": "error", "job": name, "issue": "missing_prompt_file_field"})
            elif prompt_file:
                full_path = ROOT / prompt_file
                if not full_path.exists():
                    issues.append({
                        "severity": "error",
                        "job": name,
                        "issue": "missing_repo_prompt_file",
                        "path": prompt_file,
                    })

    for name in sorted(live_names - matched_live_names):
        issues.append({"severity": "warn", "job": name, "issue": "untracked_live_job"})

    return issues


def summary_payload(
    profile: str | None,
    registry: dict[str, dict[str, Any]],
    live_count: int,
    runtime_only_names: list[str],
    environment_issue: dict[str, str] | None,
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "profile": profile or "default",
        "registry_jobs": len(registry),
        "live_jobs": live_count,
        "errors": sum(1 for item in issues if item["severity"] == "error"),
        "warnings": sum(1 for item in issues if item["severity"] == "warn"),
        "runtime_only_jobs": len(runtime_only_names),
        "runtime_only_job_names": runtime_only_names,
        "environment_issue": environment_issue,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    parser.add_argument(
        "--profile",
        default=os.getenv(PROFILE_ENV),
        help=f"Hermes profile to inspect; defaults to ${PROFILE_ENV}, then default profile",
    )
    args = parser.parse_args()

    profile = args.profile.strip() if args.profile else None
    registry = load_registry()
    runtime_only_names = runtime_only_job_names(registry)
    try:
        live = get_live_jobs(profile)
    except RuntimeError as exc:
        issue = {"kind": "live_command_failed", "profile": profile or "default", "message": str(exc)}
        summary = summary_payload(profile, registry, 0, runtime_only_names, issue, [])
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2
    environment_issue = live_environment_issue(registry, live, profile)
    if environment_issue:
        summary = summary_payload(profile, registry, len(live), runtime_only_names, environment_issue, [])
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    issues = compare(registry, live)
    summary = summary_payload(profile, registry, len(live), runtime_only_names, None, issues)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["errors"]:
        return 1
    if args.strict and summary["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
