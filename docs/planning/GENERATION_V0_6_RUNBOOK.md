# GENERATION_V0_6_RUNBOOK

> 목표: cycle close 직후 lineage 링크(커밋/PR) 보강까지 한 번에 실행한다.

## Added in v0.6
- `scripts/finalize_generation_cycle.py` 추가
- 실행 체인:
  1) `close_generation_cycle.py`
  2) `map_lineage_commit_links.py`
  3) `map_lineage_pr_links.py`

## Why
- close 이벤트가 append된 직후 링크 보강을 자동으로 이어서 처리
- 운영자가 수동으로 3개 명령을 따로 실행할 필요 제거

## Command
```bash
python3 scripts/finalize_generation_cycle.py
```

## Expected
- `lineage/generation_cycle_state.json` 갱신
- `lineage/events.jsonl` close 이벤트 append(or dedupe skip)
- 가능한 항목의 `links.commit` / `links.pr` 보강
