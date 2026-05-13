# GENERATION_V0_4_RUNBOOK

> 목표: generation 상태를 UI에서 즉시 관찰 가능하게 만든다.

## Added in v0.4
- Control bar에 generation cycle 배지 추가
- 우측 패널에 generation history 미니 타임라인 추가

## Data Sources
- `lineage/generation_cycle_state.json`
- `lineage/generation_history.jsonl`

## UI Rules
- cycle 배지:
  - GREEN -> `🟢`
  - YELLOW -> `🟡`
  - RED -> `🔴`
  - missing/error -> `?`
- history 패널:
  - 최근 8개 승급 레코드 표시
  - 형식: `promoted_at · wave_id · profile_id · score`

## Verify
```bash
python3 -m http.server 8787
# http://127.0.0.1:8787/dashboard/index.html
```
- 상단에 `generation: ...` 배지 표시
- 우측에 generation history 항목 표시
