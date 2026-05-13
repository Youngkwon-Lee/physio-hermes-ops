#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"


def repo_http_url() -> str:
    url = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
    if url.startswith("git@github.com:"):
        owner_repo = url.split(":", 1)[1].removesuffix(".git")
        return f"https://github.com/{owner_repo}"
    return url.removesuffix(".git")


def recent_commits(limit: int = 200):
    out = subprocess.check_output(
        ["git", "log", f"-n{limit}", "--date=iso-strict", "--pretty=%H|%ad|%s"],
        cwd=ROOT,
        text=True,
    )
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        h, d, s = line.split("|", 2)
        rows.append({"sha": h, "date": d, "subject": s})
    return rows


def pick_commit_for_event(event: dict, commits: list[dict]) -> str | None:
    # 1) report filename hint: dispatch_wave-2_task5_... -> commit subject may contain 'wave-2'
    report = ((event.get("links") or {}).get("report") or "")
    wave = str(event.get("wave_id") or "")
    profile = str(event.get("profile_id") or "")

    hints = [h for h in [wave, profile] if h]
    if report:
        m = re.search(r"wave-\d+", report)
        if m:
            hints.append(m.group(0))

    for c in commits:
        subj = c["subject"].lower()
        if all(h.lower() in subj for h in hints[:1]):
            return c["sha"]

    # fallback: latest commit
    return commits[0]["sha"] if commits else None


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    base = repo_http_url()
    commits = recent_commits(200)

    lines = EVENTS_PATH.read_text(encoding="utf-8").splitlines()
    out_lines = []
    changed = 0

    for line in lines:
        s = line.strip()
        if not s:
            continue
        e = json.loads(s)
        links = e.setdefault("links", {"commit": None, "pr": None, "report": None})
        if links.get("commit"):
            out_lines.append(json.dumps(e, ensure_ascii=False))
            continue

        sha = pick_commit_for_event(e, commits)
        if sha:
            links["commit"] = f"{base}/commit/{sha}"
            changed += 1
        out_lines.append(json.dumps(e, ensure_ascii=False))

    EVENTS_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"updated={changed}")


if __name__ == "__main__":
    main()
