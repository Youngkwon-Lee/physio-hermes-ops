# FRONTEND_UI_POLISH_V1

## 변경 파일
- `docs/planning/smoke_sandbox/ui_mock.tsx`

## UI 변경 요약
1. 로그인 오류 메시지 최종 카피를 mock 안에 직접 추가했다.
2. 오류 박스를 `role="alert"`, `aria-live="polite"`, `border border-rose-200 bg-rose-50`, `leading-6` 기준으로 정리했다.
3. KPI 카드를 3개로 늘리고 `grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3`로 간격 기준을 통일했다.
4. 카드 내부 spacing도 `px-4 py-4`, `space-y-1`, `min-h-[112px]`로 고정했다.

## 작업별 evidence

### 1) 로그인 오류 메시지 가독성 개선
- 파일 경로: `docs/planning/smoke_sandbox/ui_mock.tsx`
- 최종 한국어 문구:
  - `이메일 또는 비밀번호를 다시 확인해 주세요. 계속 안 되면 잠시 후 다시 시도해 주세요.`
- 가독성 메모:
  - 2문장, 기술 용어 없음, `leading-6` + 연한 배경/진한 텍스트 대비로 읽기 쉽게 유지.

### 2) 대시보드 KPI 카드 간격 불일치 수정
- 파일 경로: `docs/planning/smoke_sandbox/ui_mock.tsx`
- spacing 관련 class/token:
  - wrapper: `space-y-6`, `p-6`
  - grid: `grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3`
  - card: `min-h-[112px]`, `px-4 py-4`, `space-y-1`
- 데스크톱/태블릿 확인 메모:
  - 태블릿 `md:grid-cols-2`, 데스크톱 `xl:grid-cols-3` 기준으로 같은 gap을 유지하게 구성.
  - 다중 카드 기준 검토 가능 상태로 보강됨.

## 로컬 확인 결과
- 파일 열람 기준으로 seed scope 1, 2번 UI 요구사항을 모두 mock 한 파일에서 추적 가능하게 정리했다.
- 별도 `pnpm lint`는 이 레포에 Node/TS 프로젝트 설정(`package.json`, `tsconfig`)이 없어 실행 대상이 없었다.

## 남은 리스크
- 실제 앱 컴포넌트 반영은 아직 아님. 현재는 sandbox evidence 보강 단계다.
- 브라우저 렌더 스크린샷/실측 spacing 증거는 QA 단계에서 추가 확인이 필요하다.
