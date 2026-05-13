# BACKEND_HARDENING_V1

## 변경 파일
- `docs/planning/smoke_sandbox/backend_mock.ts`

## 백엔드 로직 강화 요약
1. 기존 `normalizeScore(x: number)`는 유지하되, 비정상 숫자 입력 시 0으로 안전 처리하도록 보강했다.
2. 반올림(`Math.round`) 후 clamp(`0~100`)를 적용해 소수점 입력도 일관된 정수 점수로 정리한다.
3. `normalizeScoreWithMeta(input: unknown)`를 추가해 누락값, 비유한수, 범위 이탈을 구분 기록할 수 있게 했다.
4. `isClamped`, `issue`, `sanitized`를 함께 반환해 QA/로그에서 왜 값이 보정됐는지 추적 가능하게 했다.

## 작업별 evidence
- 파일 경로: `docs/planning/smoke_sandbox/backend_mock.ts`
- 유지된 기본 clamp 라인: `Math.max(0, Math.min(100, value))`
- 추가 방어 포인트:
  - `input == null || input === ''`
  - `!Number.isFinite(numeric)`
  - `Math.round(numeric)`
  - `issue: 'missing' | 'not-finite' | 'below-range' | 'above-range'`

## 검증 메모
- 실행 시각: `2026-05-13T15:03:37+09:00`
- 실행 명령:
  - `npx -y tsx -e "import { normalizeScore, normalizeScoreWithMeta } from './docs/planning/smoke_sandbox/backend_mock.ts'; const checks = { neg: normalizeScore(-12), float: normalizeScore(49.8), high: normalizeScore(999), strMeta: normalizeScoreWithMeta('88.4'), infMeta: normalizeScoreWithMeta(Infinity) }; console.log(JSON.stringify(checks, null, 2));"`
- 결과 요약:
  - `normalizeScore(-12) -> 0`
  - `normalizeScore(49.8) -> 50`
  - `normalizeScore(999) -> 100`
  - `normalizeScoreWithMeta('88.4').normalized -> 88`
  - `normalizeScoreWithMeta(Infinity).issue -> 'not-finite'`
- exit code: `0`
- 목적:
  - seed scope의 단순 clamp 샘플을 실제 운영 로그/QA에서 재사용 가능한 방어형 샘플로 확장

## 남은 리스크
- 현재는 sandbox 예시 코드라 실제 API/DB 계층 연결은 아직 없다.
- repo에 `package.json`/`tsconfig`가 없어 project-level `pnpm lint` 기준은 여전히 별도 정비가 필요하다.
