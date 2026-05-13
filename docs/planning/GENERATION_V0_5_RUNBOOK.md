# GENERATION_V0_5_RUNBOOK

> 목표: generation cycle close 결과를 lineage timeline(events.jsonl)에 자동 적재한다.

## Added in v0.5
- `close_generation_cycle.py`가 cycle state 파일 생성 후
- `events.jsonl`에 **orchestrator close event** 1건을 append

## Event Mapping
- decision GREEN  -> status PASS
- decision YELLOW -> status CHECK
- decision RED    -> status FAIL

## Dedupe Rule
- 같은 wave에 대해 `run_id = generation-close-<wave>` 이벤트가 이미 있으면 append skip

## Output
- `lineage/generation_cycle_state.json`
- `lineage/events.jsonl` (close event 추가)

## Verify
```bash
python3 scripts/close_generation_cycle.py
```