# NIGHTLY_TIMEOUT_POLICY_V0_1

nightly/스모크 실행 타임아웃 표준.

## 1) 기본값
- 전체 웨이브: `MAX_DURATION_SECONDS=25200` (7h)
- 작업당 상한: `TASK_TIMEOUT_SECONDS=1800` (30m)
- lint 탐색 상한: `LINT_DISCOVERY_SECONDS=240` (4m)

## 2) 프로필 one-shot 표준
- planner/frontend/backend: `timeout 120s`
- qa/orchestrator: `timeout 240s`

## 3) 종료코드 규칙
- `0`: 정상 완료
- `124`: timeout
  - 산출물 있으면 `PASS*`
  - 산출물 없으면 `CHECK`

## 4) 재시도 규칙
1) 동일 프롬프트로 timeout 1.5배 재실행
2) 재실패 시 프롬프트 범위 축소
3) 최대 2회 후 `po`가 재배정

## 5) 실행 패턴
- 짧은 작업: foreground + timeout
- 긴 작업: background + poll/notify

## 6) 적용 기준(physio_app)
- `run_overnight_window.sh`: `MAX_DURATION_SECONDS=25200`
- `run_overnight_custom.sh`: `TASK_TIMEOUT_SECONDS=1800`, `LINT_DISCOVERY_SECONDS=240`
