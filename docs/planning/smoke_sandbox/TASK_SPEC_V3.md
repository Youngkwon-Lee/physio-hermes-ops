# TASK_SPEC_V3

seed:
- source_event: `evt-20260513-001`
- source_artifact: `docs/planning/smoke_sandbox/TASK_SPEC_V2.md`
- refinement_inputs:
  - `docs/planning/smoke_sandbox/QA_VERIFY_V2.md`
  - `docs/planning/smoke_sandbox/ORCH_STATUS_V2.md`
  - `docs/planning/SMOKE_REHEARSAL_V0_2.md`

refinement summary:
- V2는 작업 구조는 좋았지만 실제 증거가 비어 있어 완료 판정이 어려웠다.
- V3는 각 작업에 "필수 산출물"과 "증거 기준"을 추가해 PASS 판단 가능성을 높인다.
- 문서 정리 완료와 실제 검증 완료를 분리해서 기록하도록 명확화한다.

## 1. 로그인 오류 메시지 가독성 개선
- 작업: 실제 로그인 에러 UI 또는 sandbox 기준 파일에 최종 한국어 오류 문구를 추가하고, 짧고 명확한 카피로 정리한다.
- 필수 산출물:
  - 최종 오류 문구가 들어간 기준 파일 1개 이상
  - QA 문서에 동일 문구를 그대로 복사한 evidence 메모
- Acceptance Criteria:
  - 오류 문구가 1~2문장 안에서 바로 이해된다.
  - 내부 구현/기술 용어가 사용자 문구에 노출되지 않는다.
  - 실패 상태에서도 줄바꿈/대비 기준으로 읽기 어렵지 않다.
  - "최종 카피 위치"가 파일 경로 기준으로 추적 가능하다.
- Evidence:
  - 파일 경로
  - 최종 한국어 문구 원문
  - 가독성 메모 1줄
- Verify Command:
  - `pnpm lint`

## 2. 대시보드 KPI 카드 간격 불일치 수정
- 작업: KPI 카드를 2개 이상 기준으로 간격/정렬이 일관되도록 정리하고, 데스크톱·태블릿 기준 확인 근거를 남긴다.
- 필수 산출물:
  - 2개 이상 카드가 보이는 목업 또는 실제 컴포넌트 코드/스냅샷
  - spacing 판단 근거를 적은 QA 메모
- Acceptance Criteria:
  - 같은 행 카드의 상하/좌우 간격이 일관적이다.
  - 데스크톱/태블릿에서 레이아웃이 밀리거나 어색하지 않다.
  - 기존 KPI 텍스트/수치 표시가 깨지지 않는다.
  - 단일 카드가 아닌 다중 카드 기준으로 검토 가능하다.
- Evidence:
  - 파일 경로 또는 캡처 기준 경로
  - spacing 관련 class/token 목록
  - 데스크톱/태블릿 확인 메모
- Verify Command:
  - `pnpm lint`

## 3. verify 명령 정리 + 실행 증거 남기기
- 작업: 검증 명령을 한 기준으로 통일해 문서화하고, 최소 1회 실제 실행 결과를 남긴다.
- 필수 산출물:
  - 최종 verify 명령 1세트
  - 실행 성공/실패 여부와 로그 요약
  - 문서 정리 완료와 실제 실행 완료를 구분한 판정 메모
- Acceptance Criteria:
  - 대표 verify 명령이 문서에 명확히 1세트 이상 적혀 있다.
  - 중복되거나 모호한 verify 표현이 제거된다.
  - 팀원이 그대로 복붙해 실행할 수 있다.
  - 실행 여부가 PASS / PASS* / FAIL 문맥으로 구분 기록된다.
- Evidence:
  - 최종 verify 명령 원문
  - 실행 시각
  - exit code 또는 결과 요약
- Verify Command:
  - `pnpm lint && pnpm exec jest --runInBand`

## 운영 메모
- PASS 기준은 "문서 존재"만으로 충분하지 않고, 각 작업별 evidence가 채워져야 한다.
- PASS*는 timeout/부분 제약이 있어도 산출물과 증거가 남아 있을 때만 허용한다.
- 다음 wave에서는 QA/Orchestrator가 V2가 아니라 V3를 기준 문서로 참조해야 한다.
