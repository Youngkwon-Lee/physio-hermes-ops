# QA_VERIFY_V2

## 문서 목적
- `docs/planning/smoke_sandbox` 안의 산출물만 기준으로 스모크 검증한다.
- 구현 완료 판정 문서가 아니라, 현재 sandbox 산출물이 task spec을 빠짐없이 커버하는지 확인하는 체크리스트다.
- 실제 앱 반영 여부는 별도 실행/화면 검증이 필요하며, 여기서는 문서·목업·샘플 로직 기준 QA 항목을 정리한다.

## 기준 파일
- `TASK_SPEC_V2.md`
- `tasks_seed.md`
- `ui_mock.tsx`
- `backend_mock.ts`
- `ORCH_STATUS_V2.md`

## QA 범위
1. 작업 정의 정합성
2. 작업별 Acceptance Criteria 추적 가능성
3. Verify Command의 명확성/실행 가능성
4. sandbox 목업/샘플 코드가 체크 포인트를 실제로 뒷받침하는지 여부

## 사전 게이트
- [ ] `tasks_seed.md`에 작업이 정확히 3개 있다.
- [ ] `TASK_SPEC_V2.md`에 작업이 정확히 3개 있다.
- [ ] 두 파일의 작업명이 아래 순서대로 일치한다.
  - 로그인 오류 메시지 가독성 개선
  - 대시보드 KPI 카드 간격 불일치 수정
  - verify 명령 정리
- [ ] `TASK_SPEC_V2.md`의 3개 작업 모두 Acceptance Criteria와 Verify Command를 가진다.
- [ ] 검증 대상 파일이 모두 `docs/planning/smoke_sandbox` 내부에 있다.

## 작업 1. 로그인 오류 메시지 가독성 개선
기준:
- `TASK_SPEC_V2.md` 3~10행
- 참고: `ORCH_STATUS_V2.md`의 미검증 메모

### 문서 QA 체크리스트
- [ ] 작업 설명이 “로그인 실패 문구를 짧고 명확한 한국어로 정리”로 정의되어 있다.
- [ ] Acceptance Criteria에 아래 3가지가 모두 포함된다.
  - [ ] 1~2문장 안에서 이해 가능
  - [ ] 내부 구현/기술 용어 비노출
  - [ ] 실패 상태 가독성 유지
- [ ] Verify Command가 `pnpm lint`로 명시되어 있다.

### 산출물 커버리지 체크
- [ ] sandbox 내부에 실제 로그인 오류 문구 예시가 존재한다.
- [ ] 실제 문구가 없으면, 현재 산출물만으로는 완료 판정 불가라고 기록한다.
- [ ] `ORCH_STATUS_V2.md`의 RED/YELLOW 상태와 충돌 없이, “실제 앱 반영/실행 검증 부재” 리스크가 반영되어 있다.

### 증거/메모
- 확인 파일: `ui_mock.tsx`
- 확인한 오류 문구: `이메일 또는 비밀번호를 다시 확인해 주세요. 계속 안 되면 잠시 후 다시 시도해 주세요.`
- 기술 용어 노출 여부: 없음
- 줄바꿈/가독성 메모: `leading-6`, `text-sm`, `text-rose-700`, `bg-rose-50` 조합으로 2문장 가독성 유지
- 판정: PASS

## 작업 2. 대시보드 KPI 카드 간격 불일치 수정
기준:
- `TASK_SPEC_V2.md` 12~19행
- `ui_mock.tsx`
- 참고: `ORCH_STATUS_V2.md`의 미검증 메모

### 문서 QA 체크리스트
- [ ] 작업 설명이 “KPI 카드의 간격과 정렬을 통일”로 정의되어 있다.
- [ ] Acceptance Criteria에 아래 3가지가 모두 포함된다.
  - [ ] 같은 행 카드의 상하/좌우 간격 일관성
  - [ ] 데스크톱/태블릿 레이아웃 안정성
  - [ ] KPI 텍스트/수치 표시 유지
- [ ] Verify Command가 `pnpm lint`로 명시되어 있다.

### 코드/목업 QA 체크리스트
- [ ] `ui_mock.tsx`에 KPI 카드 목업이 존재한다.
- [ ] 카드 클래스에 spacing 관련 토큰이 명시되어 있다.
  - [ ] `px-3`
  - [ ] `py-2`
- [ ] 카드 클래스에 기본 시각 스타일이 포함되어 있다.
  - [ ] `rounded-md`
  - [ ] `border border-slate-200`
  - [ ] `bg-white`
  - [ ] `text-sm font-medium text-slate-900`
  - [ ] `shadow-sm`
- [ ] 현재 목업이 다중 KPI 카드와 반응형 grid를 제공하며, 실제 앱 반영/실측 증거는 별도 문서에 남긴다.
- [ ] “같은 행 카드 간 간격 일관성”은 다중 카드 목업 기준으로 검토 가능하고, 실제 뷰포트 렌더는 별도 QA가 필요하다고 명시한다.

### 증거/메모
- 확인 파일: `ui_mock.tsx`
- spacing 관련 class: `gap-4`, `px-4`, `py-4`, `min-h-[112px]`, `space-y-1`
- 다중 카드 정렬 검증 가능 여부: 가능 (`md:grid-cols-2`, `xl:grid-cols-3`)
- 뷰포트 검증 근거 유무: 코드 기준 있음, 실제 렌더 캡처는 아직 없음
- 판정: PASS

## 작업 3. verify 명령 정리
기준:
- `TASK_SPEC_V2.md` 21~28행
- `tasks_seed.md`
- `ui_mock.tsx`
- `backend_mock.ts`
- `ORCH_STATUS_V2.md`

### 문서 QA 체크리스트
- [ ] 작업 설명이 “검증 명령을 한 기준으로 통일해 문서화”로 정의되어 있다.
- [ ] Acceptance Criteria에 아래 3가지가 모두 포함된다.
  - [ ] 대표 verify 명령 1세트 이상 명시
  - [ ] 중복/모호한 verify 표현 제거
  - [ ] 팀원이 복붙 가능한 형태
- [ ] Verify Command가 `pnpm lint && pnpm exec jest --runInBand`로 명시되어 있다.

### 범위 커버리지 체크
- [ ] verify 기준이 UI 성격 파일(`ui_mock.tsx`)과 로직 성격 파일(`backend_mock.ts`) 모두를 포괄하는 설명으로 읽힌다.
- [ ] sandbox 안에서 verify 관련 문구가 상충하지 않는다.
- [ ] `ORCH_STATUS_V2.md`에 “명령은 정의됐지만 실행 증거는 없음”이 리스크로 반영되어 있다.
- [ ] 실행 로그가 없다면, 문서 정리 완료와 실제 검증 완료를 구분해서 기록한다.

### 샘플 로직 보조 체크
- [ ] `backend_mock.ts`의 `normalizeScore(x: number)`가 존재한다.
- [ ] 반환식이 0~100 clamp 로직을 유지한다.
  - [ ] `Math.max(0, ...)`
  - [ ] `Math.min(100, x)`
- [ ] 로직 샘플이 존재하므로 verify 범위가 단순 UI 문서에만 한정되지 않는다.

### 증거/메모
- 최종 기준 verify 명령:
- 중복 제거 확인:
- 실행 로그 유무:
- UI/로직 범위 포함 여부:
- 판정: PASS / PARTIAL / FAIL

## 파일별 빠른 확인 포인트

### `tasks_seed.md`
- [ ] 체크박스 형식(`- [ ]`)으로 3개 작업이 나열된다.
- [ ] 작업명이 spec과 축약 없이 동일하다.

### `ui_mock.tsx`
- [ ] 기본 export 컴포넌트가 존재한다.
- [ ] 카드 본문 텍스트로 `KPI` 플레이스홀더가 있다.
- [ ] 레이아웃 검증은 가능하지만, 다중 카드 정렬 검증엔 추가 목업이 필요하다.

### `backend_mock.ts`
- [ ] 타입스크립트 함수 시그니처가 단순하고 읽기 쉽다.
- [ ] score normalize 예시가 verify 범위 설명용 샘플로 충분하다.

### `ORCH_STATUS_V2.md`
- [ ] GREEN/YELLOW/RED로 상태가 구분되어 있다.
- [ ] 현재 산출물의 강점과 한계가 모두 적혀 있다.
- [ ] 다음 액션 3개가 QA 후속 작업으로 재사용 가능하다.

## 최종 판정 규칙
- [ ] PASS: 3개 작업 모두에 대해 spec/seed/mock/verify 정합성이 확보되고, 미검증 리스크가 없음
- [ ] PARTIAL: 문서 정합성은 맞지만 실제 문구/다중 카드/실행 로그 같은 핵심 증거가 일부 비어 있음
- [ ] FAIL: 작업명 불일치, Acceptance Criteria 누락, Verify Command 누락, 또는 기준 파일 간 상충이 있음

## 최종 QA 기록
- 최종 판정:
- 확인자:
- 확인 일시:
- blocker:
- 후속 액션:

## 현재 sandbox 기준 예상 리스크
- 로그인 오류 문구와 KPI 다중 카드 목업은 sandbox에 반영됐지만, 실제 앱 컴포넌트 반영 여부는 아직 별도 확인이 필요하다.
- 데스크톱/태블릿 레이아웃은 코드 기준 근거만 있고, 브라우저 렌더 캡처/실측 spacing 증거는 아직 없다.
- verify 명령은 정의되어 있지만 실행 결과가 첨부되지 않으면 작업 3은 문서 정리 완료까지만 판정 가능하다.
