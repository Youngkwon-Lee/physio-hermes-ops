# HERMES_SYSTEM_MAP

문서 목적: physio_app ↔ Hermes ↔ ops repo ↔ Discord/wiki 사이의 **책임 경계**를 한 장으로 고정한다.  
이 문서는 구현 세부보다 **무엇을 어디에 두는지**를 명확히 하는 데 초점을 둔다.

> 주의: 공개-safe 문서다. 토큰, private thread ID, OAuth 파일 실경로, 개인 raw data는 적지 않는다.

---

## 1. 한 줄 요약

- **physio_app** = 사용자/운영자 UI와 제품 워크플로 진입점
- **Hermes runtime** = 상태 전이, 자동화 실행, artifact 생성 엔진
- **physio-hermes-ops** = 운영 명세, 프롬프트/스크립트 원본, runbook, 점검 스크립트의 Git SSOT
- **Discord / wiki raw / cron output** = human-facing delivery 및 runtime 기록층

---

## 2. 4층 구조

### Layer A. Product / UI layer (`physio_app`)
역할:
- Mission Control, 운영 대시보드, 액션 버튼, 상태 시각화
- React / Next.js / lucide / `@/` alias 같은 UI 프레임워크 의존성 소유
- 사용자 입력을 받아 Hermes 호출 또는 SDK/API 호출로 변환

이 레이어에 남겨야 하는 것:
- 화면 컴포넌트
- icon, view model, UX state
- Next.js route / server action / client action
- UI 전용 formatting

이 레이어에 두지 말아야 하는 것:
- Hermes 내부 상태 전이 로직의 실본체
- agent lane orchestration 핵심 규칙
- eval/failure/trace artifact 생성 책임

---

### Layer B. Hermes runtime / agent-os layer
역할:
- 상태 전이
- 실행 lane 관리
- orchestration
- artifact 생성
- workflow registry / daily ops / PRD→Issue→PR→Deploy 흐름 제어

원칙:
- **React / Next / lucide / app alias 없이 순수 런타임 코드**로 유지
- UI와 분리된 TypeScript/JS runtime으로 독립 테스트 가능해야 함
- 입력: 명령/이벤트/작업 요청
- 출력: 상태 변화, runs, traces, failures, workflow artifacts

이 레이어가 소유하는 대표 개념:
- runtime
- harness
- workflows
- permissions / failures / traces
- agent lanes / orchestrator
- runs / evals

---

### Layer C. Ops source-of-intent layer (`physio-hermes-ops`)
역할:
- 운영 문서화
- cron registry
- prompt source
- script source (public-safe)
- runbook
- drift check
- architecture docs

즉, 여기서는 **실행 그 자체보다 실행을 재현/감사/이해하는 문서와 원본**을 관리한다.

포함 예:
- `cron/registry/jobs.yaml`
- `cron/prompts/*.md`
- `cron/scripts/*`
- `docs/runbook/*`
- `docs/architecture/*`
- `scripts/check_cron_registry.py`

---

### Layer D. Delivery / runtime record layer
역할:
- 실제 사용자 전달
- 실행 산출물 저장
- 운영 감사 흔적 보존

대표 위치:
- Discord thread/message
- Hermes cron output
- wiki raw summary
- local runtime state

원칙:
- human-facing message는 짧게
- raw/log/state는 runtime 쪽에 남김
- private raw data는 Git repo에 커밋하지 않음

---

## 3. 데이터/제어 흐름

```text
physio_app UI
  -> Hermes client / SDK / API wrapper
    -> Hermes runtime (state transitions / orchestration / workflows)
      -> artifacts / traces / failures / runs
        -> Discord delivery / wiki raw / cron output
          -> physio-hermes-ops docs mirror intent, rules, prompts, scripts, runbooks
```

핵심 포인트:
- **실행 truth**는 runtime에 있다.
- **설계 truth / 문서화된 intent**는 ops repo에 있다.
- **사용자 경험**은 physio_app가 소유한다.

---

## 4. 현재 권장 경계

### physio_app가 소유
- Mission Control UI
- action handlers의 UI binding
- operator interaction flow
- loading/error presentation
- icon/view formatting

### Hermes runtime가 소유
- lane state machine
- orchestration rules
- workflow registry
- artifact schema/output generation
- runs/evals/permissions/failures/traces lifecycle

### physio-hermes-ops가 소유
- cron/system architecture docs
- public-safe source mirror
- operational verification scripts
- runbooks / specs / quality standards

---

## 5. physio_app ↔ Hermes 연동 원칙

권장 방향:
1. physio_app는 Hermes 구현체를 직접 깊게 import하지 않는다.
2. 가능하면 **SDK/API boundary**를 둔다.
3. `mission-control.actions.ts`는 얇은 wrapper로 축소한다.
4. UI는 "무슨 액션을 요청할지"만 알고, 실행 엔진 상세는 Hermes가 소유한다.

이유:
- 프론트엔드 변경이 runtime 로직을 오염시키지 않게 함
- Hermes를 cron/CLI/API 어디서든 재사용 가능하게 함
- 테스트를 UI 테스트와 runtime 테스트로 분리 가능하게 함
- artifact schema와 상태 전이를 제품 UI보다 더 안정적으로 유지 가능

---

## 6. 다음 단계 옵션

### Option A. `packages/sdk`
목표:
- physio_app이 Hermes runtime 내부 모듈 직접 import 대신 SDK/API contract를 통해 호출

장점:
- boundary가 명확해짐
- laptop/dev/prod 환경 차이를 흡수하기 쉬움
- 나중에 외부 worker나 다른 app에서도 동일 contract 재사용 가능

주의:
- SDK surface가 너무 커지면 사실상 runtime leakage가 된다
- 우선 read/write use case 몇 개만 최소 인터페이스로 시작하는 것이 좋다

---

### Option B. `mission-control.actions.ts` thin wrapper화
목표:
- 현재 UI action 파일을 Hermes client 호출만 담당하는 얇은 레이어로 축소

장점:
- 지금 구조를 크게 흔들지 않고 빠르게 경계 정리 가능
- physio_app 쪽 복잡도 감소
- 차후 SDK/API 추출의 중간 단계로 좋음

주의:
- wrapper 안에 다시 비즈니스 로직이 쌓이면 경계가 다시 무너짐
- "thin" 원칙을 문서/리뷰 기준으로 강하게 유지해야 함

---

## 7. 추천 순서

현재 상태에서는 아래 순서가 가장 보수적이고 안전하다.

1. `mission-control.actions.ts`를 얇은 Hermes client wrapper로 축소
2. 실제 호출 패턴 3~5개가 안정되면 `packages/sdk` 추출
3. 이후 SDK contract를 기준으로 runtime / UI / ops 문서 정합성 유지

이 순서를 권장하는 이유:
- 바로 SDK로 가면 추상화가 너무 이르게 고정될 수 있음
- 먼저 얇은 wrapper로 실제 경계를 확인한 뒤 SDK를 만들면 surface를 더 작고 정확하게 설계할 수 있음

---

## 8. 운영 메모

- `physio-hermes-ops`는 runtime state 저장소가 아니다.
- runtime output, secrets, local state는 Hermes 쪽에 남긴다.
- ops repo에는 **공개-safe source, architecture, checks, runbook**만 올린다.
- 구조가 흔들릴 때는 "이 로직이 UI concern인가, runtime concern인가, ops concern인가"를 먼저 물어본다.
