# TASK_SPEC_V2

## 1. 로그인 오류 메시지 가독성 개선
- 작업: 로그인 실패 문구를 짧고 명확한 한국어로 정리한다.
- Acceptance Criteria:
  - 오류 문구가 1~2문장 안에서 바로 이해된다.
  - 내부 구현/기술 용어가 사용자 문구에 노출되지 않는다.
  - 실패 상태에서도 가독성(대비/줄바꿈)이 유지된다.
- Verify Command:
  - `pnpm lint`

## 2. 대시보드 KPI 카드 간격 불일치 수정
- 작업: KPI 카드의 간격과 정렬을 통일한다.
- Acceptance Criteria:
  - 같은 행 카드의 상하/좌우 간격이 일관적이다.
  - 데스크톱/태블릿에서 레이아웃이 밀리거나 어색하지 않다.
  - 기존 KPI 텍스트/수치 표시가 깨지지 않는다.
- Verify Command:
  - `pnpm lint`

## 3. verify 명령 정리
- 작업: 검증 명령을 한 기준으로 통일해 문서화한다.
- Acceptance Criteria:
  - 대표 verify 명령이 문서에 명확히 1세트 이상 적혀 있다.
  - 중복되거나 모호한 verify 표현이 제거된다.
  - 팀원이 그대로 복붙해 실행할 수 있다.
- Verify Command:
  - `pnpm lint && pnpm exec jest --runInBand`
