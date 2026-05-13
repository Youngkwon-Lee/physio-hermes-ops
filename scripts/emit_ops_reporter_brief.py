#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lineage = root / 'lineage' / 'events.jsonl'

rows = []
if lineage.exists():
    for line in lineage.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line:
            rows.append(json.loads(line))

now = datetime.now().strftime('%Y-%m-%d')
if not rows:
    print(f"[ops-reporter] {now}")
    print("상태: RED")
    print("이벤트: 0")
    print("이슈: lineage/events.jsonl 없음 또는 비어있음")
    print("다음: 데이터 수집 파이프라인 확인")
    raise SystemExit(0)

status = Counter(r.get('status','UNKNOWN') for r in rows)
avg = sum(float(r.get('score',0)) for r in rows)/len(rows)
if status.get('FAIL',0)>0:
    card='RED'
elif status.get('CHECK',0)>0 or status.get('PASS*',0)>0:
    card='YELLOW'
else:
    card='GREEN'

by_profile = defaultdict(lambda:[0,0.0])
for r in rows:
    p=r.get('profile_id','unknown')
    by_profile[p][0]+=1
    by_profile[p][1]+=float(r.get('score',0))
leader=max(by_profile.items(), key=lambda kv: kv[1][1]/kv[1][0])[0]

print(f"[ops-reporter] {now}")
print(f"상태: {card} | 이벤트: {len(rows)} | 평균점수: {avg:.1f}")
print("분포: " + ", ".join(f"{k}={v}" for k,v in sorted(status.items())))
print(f"리더: {leader}")
print("다음: FAIL/CHECK 우선 triage, PASS* 산출물 재검토")
