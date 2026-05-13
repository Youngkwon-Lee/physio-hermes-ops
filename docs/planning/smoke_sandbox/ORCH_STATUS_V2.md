# ORCH_STATUS_V2

기준 범위:
- `docs/planning/smoke_sandbox/TASK_SPEC_V2.md`
- `docs/planning/smoke_sandbox/QA_VERIFY_V2.md`
- `docs/planning/smoke_sandbox/tasks_seed.md`
- `docs/planning/smoke_sandbox/ui_mock.tsx`
- `docs/planning/smoke_sandbox/backend_mock.ts`

## 상태 카드

### GREEN
- `TASK_SPEC_V2.md`와 `tasks_seed.md`에 작업이 3개로 정렬돼 있고, 작업명도 동일하다.
- 3개 작업 모두 Acceptance Criteria와 Verify Command가 명시돼 있어 최소 스펙 구조는 갖춰졌다.
- `QA_VERIFY_V2.md`가 사전 게이트, 작업별 체크리스트, 최종 판정 규칙까지 포함해 QA 문서 골격을 충분히 커버한다.
- `ui_mock.tsx`와 `backend_mock.ts`가 각각 UI spacing 포인트와 로직 샘플(`normalizeScore`)을 분리해서 보여줘, sandbox 기준 확인 축은 있다.

### YELLOW
- 현재 산출물은 문서 + 목업 + 샘플 로직 중심이라 실제 앱 반영 여부는 아직 확인되지 않았다.
- `ui_mock.tsx`는 단일 KPI 카드만 있어, Acceptance Criteria의 "같은 행 카드 간 간격 일관성"은 부분 검증만 가능하다.
- Verify Command는 정리됐지만 실행 로그나 PASS 증거가 없어, "검증 가능"과 "검증 완료"는 아직 구분해야 한다.
- `QA_VERIFY_V2.md`의 증거/메모, 최종 QA 기록 섹션은 비어 있어 운영 메타데이터가 아직 없다.

### RED
- 로그인 오류 메시지의 실제 최종 한국어 카피가 sandbox 안에 없어 작업 1 완료 판정 근거가 부족하다.
- KPI 간격 수정은 실컴포넌트/실뷰포트 증거가 없어 데스크톱·태블릿 레이아웃 안정성을 아직 증명하지 못했다.
- `pnpm lint` / `pnpm exec jest --runInBand`는 문서에만 정의돼 있고 실행 결과가 없어, 작업 3도 문서 정리 수준 이상으로는 확정할 수 없다.

## 다음 액션 3개
1. 실제 로그인 에러 UI에 적용할 최종 한국어 문구를 sandbox 또는 실컴포넌트 기준 파일에 추가하고, `QA_VERIFY_V2.md` 증거란에 문구를 그대로 기록한다.
2. KPI 카드를 2개 이상 배치한 목업 또는 실제 컴포넌트 캡처/코드 스냅샷을 남겨 spacing 일관성과 뷰포트 안정성 근거를 보강한다.
3. `pnpm lint`와 필요 시 `pnpm exec jest --runInBand`를 실행한 뒤 결과를 `QA_VERIFY_V2.md`의 최종 판정/후속 액션에 반영한다.
