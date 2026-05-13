# GENERATION_V1_0_RUNBOOK

> 목표: generation-close 이벤트에서 운영 재개 판단(`resume recommendation`)을 자동 표기한다.

## Added in v1.0
- `generation close summary` 카드에 `resume_recommendation` 필드 추가
- 규칙 기반 권고를 이벤트 클릭 시 즉시 계산

## Rule
- `HOLD`:
  - decision = `RED`, 또는
  - FAIL > 0
- `LIMITED_RESUME`:
  - decision = `YELLOW`, 또는
  - CHECK > 0
- `RESUME`:
  - decision = `GREEN` 이고 FAIL/CHECK 모두 0
- 그 외: `CHECK_REQUIRED`

## UI Output
- `resume_recommendation`
- `recommendation_reason`

## Verify
```bash
python3 -m http.server 8787
# dashboard에서 GEN-CLOSE 이벤트 클릭
# generation close summary에서 recommendation 값/사유 확인
```