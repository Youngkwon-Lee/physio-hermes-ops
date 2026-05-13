#!/usr/bin/env python3
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "cron_status.json"

TARGETS = {
    "physio-wave-spawn": "wave_spawn",
    "physio-wave-dispatcher": "wave_dispatcher",
    "physio-watchdog-fail-check": "watchdog",
}


def parse_jobs(text: str):
    jobs = []
    blocks = re.split(r"\n\s*([0-9a-f]{12}\s+\[[^\]]+\])\n", text)
    if len(blocks) < 3:
        return jobs
    for i in range(1, len(blocks), 2):
        header = blocks[i].strip()
        body = blocks[i + 1]
        m = re.match(r"([0-9a-f]{12})\s+\[([^\]]+)\]", header)
        if not m:
            continue
        job_id, state_tag = m.group(1), m.group(2)
        name_m = re.search(r"Name:\s+(.+)", body)
        next_m = re.search(r"Next run:\s+(.+)", body)
        name = name_m.group(1).strip() if name_m else None
        jobs.append({
            "job_id": job_id,
            "name": name,
            "state": "paused" if "paused" in state_tag else "scheduled",
            "enabled": False if "paused" in state_tag else True,
            "next_run_at": next_m.group(1).strip() if next_m else None,
        })
    return jobs


def main():
    p = subprocess.run(["hermes", "cron", "list", "--all"], capture_output=True, text=True)
    text = (p.stdout or "") + (p.stderr or "")
    parsed = parse_jobs(text)

    rows = {k: {"name": k, "enabled": None, "state": "unknown", "next_run_at": None} for k in TARGETS}
    for j in parsed:
        if j.get("name") in rows:
            rows[j["name"]] = {
                "name": j["name"],
                "enabled": j["enabled"],
                "state": j["state"],
                "next_run_at": j["next_run_at"],
            }

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ok": p.returncode == 0,
        "raw_output_present": bool(text.strip()),
        "items": {TARGETS[k]: v for k, v in rows.items()},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(OUT))


if __name__ == "__main__":
    main()
