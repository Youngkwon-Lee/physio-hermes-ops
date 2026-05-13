# GENERATION_V0_3_RUNBOOK

> 목표: generation 루프를 한 사이클 단위로 자동 마감하고, 다음 wave를 seed 기반으로 자동 큐잉한다.

## Added in v0.3
- cycle auto-close 판정 (`scripts/close_generation_cycle.py`)
- generation seed 기반 next wave append (`scripts/append_next_wave_from_generation.py`)

## 1) Auto-close Rule
- 대상: 최신 wave의 이벤트 집합
- 판정:
  - FAIL 하나라도 있으면 `RED`
  - CHECK 또는 PASS* 있으면 `YELLOW`
  - 그 외 `GREEN`
- 출력: `lineage/generation_cycle_state.json`

## 2) Auto-seed Append Rule
- 입력:
  - `lineage/generation_state.json` (current_seed)
  - `lineage/wave_queue.jsonl`
  - `lineage/dispatch_state.json`
- 조건:
  - 이미 같은 next wave가 queue에 있으면 skip
- 출력:
  - `lineage/wave_queue.jsonl` append
  - `lineage/spawn_state.json` 갱신

## Commands
```bash
python3 scripts/close_generation_cycle.py
python3 scripts/append_next_wave_from_generation.py
```

## Notes
- v0.3는 여전히 파일 기반 Mini OS.
- v0.4에서 cycle close 결과를 대시보드 배지/타임라인 이벤트로 확장 권장.
