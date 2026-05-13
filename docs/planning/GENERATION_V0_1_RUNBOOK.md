# GENERATION_V0_1_RUNBOOK

> 목표: 파일 기반 Mini Nautilus에서 `지난 사이클 -> 다음 사이클 씨앗 승급`을 자동화한다.

## Scope (v0.1)
- seed 승급 규칙: `lineage/events.jsonl`에서 최고 점수 이벤트 선택
- generation 기록: `lineage/generation_state.json`
- PR 링크 매핑: 최근 commit을 lineage events의 `links.commit`에 반영

## Seed Promote Rule
1. 후보: status in `PASS`, `PASS*`
2. 우선순위:
   - score 높은 순
   - timestamp 최신 순
3. 산출:
   - `generation.current_seed`
   - `generation.last_promoted_at`
   - `generation.source_event_id`

## Scripts
- `scripts/promote_generation_seed.py`
  - 입력: `lineage/events.jsonl`
  - 출력: `lineage/generation_state.json`
- `scripts/map_lineage_commit_links.py`
  - 입력: `lineage/events.jsonl`, git history
  - 출력: `lineage/events.jsonl` (`links.commit` 보강)

## Commands
```bash
python3 scripts/promote_generation_seed.py
python3 scripts/map_lineage_commit_links.py
```

## Expected Output Example
- `generation_state.json`
```json
{
  "version": "v0.1",
  "current_seed": {
    "event_id": "evt-20260513-001",
    "wave_id": "wave-1",
    "profile_id": "physio-planner",
    "score": 92,
    "status": "PASS"
  }
}
```

## Notes
- v0.1은 glctl/glhub 없이 로컬 파일 기반으로 운용.
- 다음 버전(v0.2)에서 PR URL 매핑(`links.pr`) 확장 권장.