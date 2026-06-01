# PHYSIO_APP_RUNTIME_SPLIT

문서 목적: physio_app에서 진행 중인 Hermes runtime 분리 작업의 **현재 구조 변화**를 기록하고, UI / runtime / workflow 책임을 어디까지 분리할지 합의점을 남긴다.

기준 브랜치 메모:
- 작업 브랜치: `codex/agent-os-runtime-split`
- 이 문서는 브랜치 자체를 SSOT로 대체하지 않으며, 구조 의도를 설명하는 보조 문서다.

---

## 1. 이번 분리의 핵심

이번 변화의 본질은 다음 한 줄로 요약된다.

> **Hermes 쪽은 상태 전이와 artifact 생성만 소유하고, UI 전용 의존성은 physio_app에 남긴다.**

즉,
- React
- Next.js
- lucide
- `@/` alias 기반 app import

같은 요소를 runtime 계층에서 제거하고,
대신 **순수 런타임 코드**로 구조를 세운 것이다.

---

## 2. 현재 생긴 3층 묶음

### A. runtime
핵심 파일:
- `runtime/index.ts`
- `runtime/agents.ts`
- `runtime/lanes.ts`
- `runtime/orchestrator.ts`
- `runtime/runs.ts`

역할:
- agent 정의
- lane 모델
- orchestration
- run lifecycle
- runtime entrypoint

의미:
- Mission Control이나 worker orchestration의 핵심 상태 머신이 UI로부터 분리되기 시작했다.

---

### B. harness
핵심 파일:
- `harness/index.ts`
- `harness/evals.ts`
- `harness/permissions.ts`
- `harness/failures.ts`
- `harness/traces.ts`

역할:
- 평가/eval
- permission gate
- failure 분류
- trace 수집
- 검증/실험용 실행 보조 레이어

의미:
- runtime이 단순 실행 엔진에 그치지 않고, 검증 가능성과 운영 가능성을 갖춘 계층으로 정리되고 있다.

---

### C. workflows
핵심 파일:
- `workflows/index.ts`
- `workflows/registry.ts`
- `workflows/daily-ops.ts`
- `workflows/prd-to-issue.ts`
- `workflows/issue-to-pr.ts`
- `workflows/issue-to-pr-worker.ts`
- `workflows/pr-to-deploy.ts`

역할:
- workflow registry
- 일일 운영 루프
- PRD → Issue → PR → Deploy 파이프라인
- worker 단위 workflow 실행

의미:
- 제품 워크플로를 UI action이 아니라 독립된 runtime workflow로 다루기 시작했다.

---

## 3. 왜 이 분리가 중요한가

### 3-1. 재사용성
runtime 로직이 UI 프레임워크와 분리되면:
- physio_app UI
- Hermes cron
- CLI
- background worker
- future API server

모두에서 같은 core 로직을 재사용할 수 있다.

### 3-2. 테스트 가능성
현재처럼 타입 체크를 runtime / harness / workflows 각각 통과시키면,
문제가 UI에 있는지 runtime에 있는지 더 빠르게 분리할 수 있다.

### 3-3. 경계 명확화
앞으로 리뷰할 때 기준이 생긴다.
- 이 코드는 UI concern인가?
- runtime state transition인가?
- workflow policy인가?
- ops 문서/검증 concern인가?

---

## 4. 현재 검증 상태

사용자 보고 기준 확인된 검증:
- runtime 타입 체크 통과
- harness 타입 체크 통과
- workflows 타입 체크 통과

이 의미는:
- 최소한 계층 분리 후 타입 레벨 일관성은 확보되기 시작했다는 것
- 다만 아직 **호출 경계(API/SDK/wrapper)** 는 최종 정리 전 단계일 수 있다는 것

---

## 5. 다음 단계 옵션 해석

### Option 1. `packages/sdk`
의도:
- physio_app이 Hermes 내부 코드를 직접 import하기보다 SDK/API contract를 통해 호출

언제 좋은가:
- 호출 surface가 어느 정도 안정됨
- 다른 app이나 worker에서도 재사용할 계획이 있음
- runtime 구현 세부를 숨기고 싶음

리스크:
- 너무 일찍 만들면 실제 사용 패턴보다 넓은 abstraction이 생길 수 있음
- "SDK"라는 이름만 있고 사실상 내부 구조가 새어 나오는 얇지 않은 wrapper가 될 수 있음

---

### Option 2. `mission-control.actions.ts` thin wrapper화
의도:
- physio_app의 액션 파일을 Hermes client 호출만 담당하는 얇은 레이어로 축소

언제 좋은가:
- 현재 UI 쪽 결합을 빨리 낮추고 싶음
- SDK surface를 설계하기 전에 실제 호출 패턴을 관찰하고 싶음
- 리팩터링 리스크를 작게 가져가고 싶음

리스크:
- wrapper 안에 비즈니스 로직이 다시 쌓이면 구조가 재오염됨
- 리뷰 기준이 약하면 "임시"가 영구 구조가 될 수 있음

---

## 6. 권장 판단

현재 단계에서는 **Option 2를 먼저** 권장한다.

즉:
1. `mission-control.actions.ts`를 얇은 Hermes client wrapper로 줄인다.
2. 실제 read/write/execute 호출 패턴을 수집한다.
3. 그 패턴이 안정되면 `packages/sdk`를 만든다.

이 순서가 좋은 이유:
- abstraction을 너무 빨리 고정하지 않음
- 실제 Mission Control이 어떤 contract를 정말 필요로 하는지 드러남
- SDK가 생기더라도 더 작고 명확한 surface로 시작 가능

---

## 7. 리뷰 체크리스트

앞으로 이 분리 작업을 리뷰할 때는 아래를 본다.

### UI 쪽 체크
- React/Next/lucide 의존성이 runtime으로 다시 새지 않았는가?
- 화면 표현 책임이 workflow/runtime에 들어가 있지 않은가?

### runtime 쪽 체크
- 상태 전이 규칙이 UI 파일에 남아 있지 않은가?
- run/orchestrator/lane 로직이 pure runtime으로 유지되는가?

### harness 쪽 체크
- permission/failure/trace/eval 규칙이 분산되지 않고 모여 있는가?
- 운영 검증 포인트가 artifact로 남는가?

### workflows 쪽 체크
- PRD→Issue→PR→Deploy 흐름이 화면 액션에 종속되지 않는가?
- registry 기반으로 확장 가능한가?

### integration 쪽 체크
- `mission-control.actions.ts`는 thin wrapper를 유지하는가?
- SDK/API 경계가 생길 때 runtime leakage가 없는가?

---

## 8. ops repo와의 연결

이 문서가 physio-hermes-ops에 있는 이유는,
이 저장소가 코드 저장소라기보다 **운영 구조/경계/의도**를 장기 보관하는 곳이기 때문이다.

따라서 여기에는:
- 구조 의도
- layer 경계
- 권장 다음 단계
- review 기준

을 남기고,
실제 구현 코드는 physio_app 브랜치에서 진행한다.

---

## 9. 한 줄 결론

이번 분리는 단순 파일 이동이 아니라,
**physio_app는 UI를, Hermes는 runtime을, physio-hermes-ops는 운영 명세를 소유하게 만드는 구조 정리**다.
