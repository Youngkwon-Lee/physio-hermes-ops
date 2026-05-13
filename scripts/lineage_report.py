#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

p = Path('lineage/events.jsonl')
if not p.exists():
    print('no lineage/events.jsonl found')
    raise SystemExit(1)

rows = []
for line in p.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line:
        continue
    rows.append(json.loads(line))

status = Counter(r['status'] for r in rows)
by_profile = defaultdict(lambda: {'count':0, 'score':0.0})
for r in rows:
    item = by_profile[r['profile_id']]
    item['count'] += 1
    item['score'] += float(r.get('score',0))

avg_score = (sum(float(r.get('score',0)) for r in rows) / len(rows)) if rows else 0

print('# Mini Nautilus Lineage Report')
print(f'- events: {len(rows)}')
print(f'- avg score: {avg_score:.1f}')
print('- status: ' + ', '.join(f"{k}={v}" for k,v in sorted(status.items())))
print('\n## profile leaderboard')
for profile, info in sorted(by_profile.items(), key=lambda kv: kv[1]['score']/kv[1]['count'], reverse=True):
    s = info['score']/info['count']
    print(f'- {profile}: avg_score={s:.1f}, events={info["count"]}')
