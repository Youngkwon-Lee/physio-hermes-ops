#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lineage = root / 'lineage' / 'events.jsonl'

if not lineage.exists():
    print(f"🚨 [watchdog] {datetime.now():%F %T} lineage/events.jsonl 없음")
    raise SystemExit(0)

rows=[]
for line in lineage.read_text(encoding='utf-8').splitlines():
    line=line.strip()
    if line:
        rows.append(json.loads(line))

if not rows:
    print(f"🚨 [watchdog] {datetime.now():%F %T} lineage 이벤트 0건")
    raise SystemExit(0)

status=Counter(r.get('status','UNKNOWN') for r in rows)
fail=status.get('FAIL',0)
check=status.get('CHECK',0)
if fail==0 and check==0:
    # no_agent cron semantics: empty stdout => no message
    raise SystemExit(0)

print(f"🚨 [watchdog] {datetime.now():%F %T}")
print(f"FAIL={fail}, CHECK={check}, total={len(rows)}")
print("조치: 최신 morning_brief 확인 후 blocker triage")
