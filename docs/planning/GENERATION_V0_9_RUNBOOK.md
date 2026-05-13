# GENERATION_V0_9_RUNBOOK

> 목표: generation-close 이벤트를 클릭했을 때 decision/breakdown 정보를 별도 카드로 즉시 보여준다.

## Added in v0.9
- Event Detail에 `Generation Close Summary` 카드 추가
- 대상: `run_id`가 `generation-close-`로 시작하는 이벤트

## Card Fields
- decision
- wave_id
- event_count
- status_breakdown (PASS/PASS*/CHECK/FAIL)
- closed_at

## Fallback
- generation-close가 아니면 카드는 `-` 표시 유지
- report 로드 실패 시에도 기존 report 패널 동작은 유지

## Verify
```bash
python3 -m http.server 8787
# timeline에서 GEN-CLOSE 이벤트 클릭 → summary 카드 값 확인
```