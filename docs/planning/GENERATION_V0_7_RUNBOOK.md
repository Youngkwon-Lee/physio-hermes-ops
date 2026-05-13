# GENERATION_V0_7_RUNBOOK

> 목표: finalize 체인을 단일 cron 엔트리로 묶어 무인 루프 실행 기반을 만든다.

## Added in v0.7
- `~/.hermes/scripts/physio_finalize_generation_cycle.sh` 추가
- cron job `physio-generation-finalize` 추가 (기본 paused)

## Cron Script Flow
1. `python3 scripts/finalize_generation_cycle.py`
2. `python3 scripts/export_cron_status.py`

## Schedule (default)
- `every 15m`
- `no_agent=true`
- `deliver=origin`

## Safety
- 기본 생성 직후 `paused`로 둔다.
- 수동 실행으로 결과 확인 후 resume.

## Manual Verify
```bash
bash ~/.hermes/scripts/physio_finalize_generation_cycle.sh
```