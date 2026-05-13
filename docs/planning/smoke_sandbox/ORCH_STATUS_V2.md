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
- `ui_mock.tsx`가 다중 KPI 카드와 반응형 grid 기준을 포함하도록 보강됐지만, 실제 브라우저 캡처/실측 spacing 증거는 아직 없다.
- Verify Command는 정리됐지만 실행 로그나 PASS 증거가 없어, "검증 가능"과 "검증 완료"는 아직 구분해야 한다.
- `QA_VERIFY_V2.md`의 작업 1·2 evidence는 채워졌지만, 최종 QA 기록과 작업 3 실행 기록은 비어 있다.

### RED
- `pnpm lint` / `pnpm exec jest --runInBand`는 문서에만 정의돼 있고 실행 결과가 없어, 작업 3은 아직 문서 정리 수준 이상으로는 확정할 수 없다.
- 실제 앱 컴포넌트 반영 여부와 데스크톱·태블릿 렌더 결과는 별도 QA 없이 확정할 수 없다.

## 다음 액션 3개
1. sandbox에서 정리한 로그인 오류 카피와 KPI spacing mock을 실제 앱 컴포넌트 후보 경로에 옮길지 결정한다.
2. 브라우저 또는 캡처 기반으로 데스크톱·태블릿 렌더 결과를 남겨 spacing 일관성 근거를 보강한다.
3. `pnpm lint`와 필요 시 `pnpm exec jest --runInBand`를 실행한 뒤 결과를 `QA_VERIFY_V2.md`의 최종 판정/후속 액션에 반영한다.
