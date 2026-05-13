# NIGHTLY_PROFILE_RUNBOOK_V0_1

physio_app Hermes 멀티프로필 nightly 운영 runbook.

## 0) 목표
- 고정 플로우: `pp → pf/pb → pq → po`
- 실패 시 아침 인계 가능한 상태카드(GREEN/YELLOW/RED) 보장

## 1) 단계별 책임
### Stage A — Plan Gate (pp)
- 입력: backlog, known issue
- 출력: 실행 task list, acceptance criteria, verify command draft

### Stage B — Build Wave (pf/pb)
- pf: UI/interaction
- pb: API/logic/runtime
- 출력: 변경 파일/핵심 diff, 로컬 검증 결과

### Stage C — Verify Gate (pq)
- lint/typecheck/unit/smoke 수행
- 출력: pass/fail matrix, 재현 스텝, 로그

### Stage D — Orchestrate Decision (po)
- merge/hold/rollback/retry 결정
- 아침 인계 summary + next seed 작성

## 2) 실패 처리
- Class-1: 즉시 차단(빌드 불가/핵심 경로 파손)
- Class-2: 조건부 진행(우회 가능)
- Class-3: 기록 후 진행(경미)

재시도: 동일 실패 최대 2회, 이후 `po`가 범위 축소/재배정.

## 3) 상태 카드
- GREEN: 핵심 검증 통과
- YELLOW: 제한적 진행
- RED: 차단 이슈

## 4) Timeout 정책 연동
- 기준 문서: `docs/planning/NIGHTLY_TIMEOUT_POLICY_V0_1.md`
- 판정 규약:
  - PASS: exit 0 + 산출물 존재
  - PASS*: exit 124(timeout) + 산출물 존재
  - CHECK: timeout/오류 + 산출물 미생성
  - FAIL: 차단 이슈
