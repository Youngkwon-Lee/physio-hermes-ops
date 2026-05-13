#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lineage = root / 'lineage' / 'events.jsonl'
out_dir = root / 'docs' / 'reports'
out_dir.mkdir(parents=True, exist_ok=True)

def load_events(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows

rows = load_events(lineage)
now = datetime.now()
date_str = now.strftime('%Y-%m-%d')
out = out_dir / f'morning_brief_{date_str}.md'

if not rows:
    md = f"# Morning Brief ({date_str})\n\n- 상태: RED\n- 원인: lineage/events.jsonl 없음 또는 이벤트 없음\n"
    out.write_text(md, encoding='utf-8')
    print(str(out))
    print(md)
    raise SystemExit(0)

status = Counter(r.get('status', 'UNKNOWN') for r in rows)
by_profile = defaultdict(lambda: {'count': 0, 'score_sum': 0.0})
for r in rows:
    p = r.get('profile_id', 'unknown')
    by_profile[p]['count'] += 1
    by_profile[p]['score_sum'] += float(r.get('score', 0))

avg_score = sum(float(r.get('score', 0)) for r in rows) / len(rows)
if status.get('FAIL', 0) > 0:
    card = 'RED'
elif status.get('CHECK', 0) > 0 or status.get('PASS*', 0) > 0:
    card = 'YELLOW'
else:
    card = 'GREEN'

leader = sorted(
    ((p, v['score_sum'] / v['count'], v['count']) for p, v in by_profile.items()),
    key=lambda x: x[1], reverse=True
)

lines = [
    f"# Morning Brief ({date_str})",
    "",
    f"- 상태: **{card}**",
    f"- 총 이벤트: {len(rows)}",
    f"- 평균 점수: {avg_score:.1f}",
    "- 상태 분포: " + ", ".join(f"{k}={v}" for k, v in sorted(status.items())),
    "",
    "## Profile 리더보드",
]
for p, s, c in leader:
    lines.append(f"- {p}: avg_score={s:.1f}, events={c}")

lines += [
    "",
    "## 다음 액션",
    "1. FAIL/CHECK 이벤트 우선 triage",
    "2. PASS* 항목은 산출물 품질 재검토",
    "3. 다음 wave seed 후보 1개 선정",
]

md = "\n".join(lines) + "\n"
out.write_text(md, encoding='utf-8')
print(str(out))
print(md)
