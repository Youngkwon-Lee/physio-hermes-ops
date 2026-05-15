#!/usr/bin/env python3
import json
from pathlib import Path

from lineage_stream_context import build_stream_context

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"


def load_rows(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            rows.append(json.loads(s))
    return rows


def main():
    rows = load_rows(EVENTS_PATH)
    if not rows:
        print("no rows")
        return

    changed = 0
    for r in rows:
        current_stream = str(r.get("stream_id") or "")
        if current_stream and current_stream != "unmapped" and (r.get("thread_id") or r.get("channel_id")):
            continue

        ctx = build_stream_context(str(r.get("run_id") or ""))
        if (not current_stream) or current_stream == "unmapped":
            r["stream_id"] = ctx["stream_id"]
            changed += 1
        # backfill only when currently missing
        for k in ("channel_id", "thread_id", "channel_name", "thread_name"):
            if not r.get(k) and ctx.get(k):
                r[k] = ctx[k]
                changed += 1

    EVENTS_PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"updated fields: {changed}, rows: {len(rows)}")


if __name__ == "__main__":
    main()
