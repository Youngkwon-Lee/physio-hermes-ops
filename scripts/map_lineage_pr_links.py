#!/usr/bin/env python3
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"


def parse_owner_repo_from_commit_url(url: str):
    # https://github.com/owner/repo/commit/<sha>
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/commit/([0-9a-fA-F]+)$", url or "")
    if not m:
        return None, None, None
    return m.group(1), m.group(2), m.group(3)


def fetch_pr_url(owner: str, repo: str, sha: str):
    api = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/pulls"
    req = urllib.request.Request(
        api,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "physio-hermes-ops-bot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

    if isinstance(data, list) and data:
        pr = data[0]
        return pr.get("html_url")
    return None


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    lines = EVENTS_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    changed = 0

    for line in lines:
        s = line.strip()
        if not s:
            continue
        e = json.loads(s)
        links = e.setdefault("links", {"commit": None, "pr": None, "report": None})
        if links.get("pr"):
            out.append(json.dumps(e, ensure_ascii=False))
            continue

        commit_url = links.get("commit")
        owner, repo, sha = parse_owner_repo_from_commit_url(commit_url)
        if owner and repo and sha:
            pr_url = fetch_pr_url(owner, repo, sha)
            if pr_url:
                links["pr"] = pr_url
                changed += 1

        out.append(json.dumps(e, ensure_ascii=False))

    EVENTS_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"updated_pr_links={changed}")


if __name__ == "__main__":
    main()
