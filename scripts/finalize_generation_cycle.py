#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_step(cmd: list[str]):
    print(f"$ {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print(res.stderr.strip())
    if res.returncode != 0:
        raise SystemExit(res.returncode)


def main():
    steps = [
        ["python3", "scripts/close_generation_cycle.py"],
        ["python3", "scripts/map_lineage_commit_links.py"],
        ["python3", "scripts/map_lineage_pr_links.py"],
    ]
    for s in steps:
        run_step(s)
    print("finalize_generation_cycle: done")


if __name__ == "__main__":
    main()
