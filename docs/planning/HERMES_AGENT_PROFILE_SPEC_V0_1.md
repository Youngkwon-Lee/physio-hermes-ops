# Hermes Agent Profile Spec v0.1 for physio_app

> **For Hermes:** 이 문서는 physio_app용 8개 agent roster를 실제 Hermes profile로 옮길 때 기준이 되는 설정 초안이다. 바로 전부 생성하기보다, 1차 5개 프로필부터 만들고 안정화 후 확장한다.

**Goal:** physio_app의 8개 agent 역할을 Hermes profiles/toolsets/model/workflow 관점에서 정의한다.

**Architecture:** profile은 역할별로 분리하되, 너무 세밀하게 쪼개지 않는다. `orchestrator`가 흐름을 잡고, `planner`가 spec을 정리하고, `frontend`/`backend`가 구현하고, `qa`가 검증한다. `designer`, `marketing`, `ops-reporter`는 2차 확장으로 붙인다.

**Tech Stack:** Hermes profiles, toolsets, kanban, terminal/file/browser, cron/nightly, session memory.

---

## 1. Naming Convention

- profile id: 영어 slug
- display name: 한글
- 기본 형식: `physio-<role>`

### 추천 profile ids
1. `physio-orchestrator`
2. `physio-planner`
3. `physio-frontend`
4. `physio-backend`
5. `physio-qa`
6. `physio-designer`
7. `physio-marketing`
8. `physio-ops-reporter`

이렇게 `physio-` prefix를 붙이면:
- 다른 프로젝트와 안 섞이고
- profile list에서 한눈에 보이고
- alias/script 관리도 쉬워진다.

---

## 2. Rollout Plan

## Phase 1 — 바로 만들 5개
- `physio-orchestrator`
- `physio-planner`
- `physio-frontend`
- `physio-backend`
- `physio-qa`

## Phase 2 — 추가 3개
- `physio-designer`
- `physio-marketing`
- `physio-ops-reporter`

### 이유
- 현재 physio_app는 build/verify 흐름이 핵심이라 5개만으로도 실제 생산성이 난다.
- 나머지 3개는 대외 문구/리포트/UX 비중이 커질 때 붙이면 된다.

---

## 3. Shared Defaults

모든 physio profiles 공통 권장값:

- working style: 한국어 응답, 짧고 핵심적으로
- repo context: `/home/yk/physio_app`
- default branch policy: `main` direct push 금지
- nightly policy: 자동 merge 금지
- verify policy: targeted verify 필수
- memory policy: 프로젝트 사실/사용자 선호만 저장

### Shared model recommendation
- 기본 추천: `gpt-5.4`
- 더 저렴한 보조 역할(planner, marketing, ops-reporter)은 이후 cheap model로 낮출 수 있음
- 구현/검증 역할(frontend, backend, qa)은 우선 같은 모델로 시작하는 게 안정적

---

## 4. Toolset Matrix

| Profile | 핵심 toolsets | 비고 |
|---|---|---|
| physio-orchestrator | file, terminal, skills, todo, session_search, messaging | kanban 중심 운영, 구현 최소화 |
| physio-planner | file, search, session_search, todo, skills | spec/문서/우선순위 |
| physio-frontend | file, terminal, browser, vision, skills | UI 구현/브라우저 smoke |
| physio-backend | file, terminal, code_execution, skills | server logic/tool runtime |
| physio-qa | file, terminal, browser, vision, skills | verify/e2e/smoke |
| physio-designer | file, browser, vision, image_gen, skills | mock/copy/UX |
| physio-marketing | file, web, search, skills, tts | launch copy/X thread |
| physio-ops-reporter | file, terminal, session_search, cronjob, messaging, skills | report/lineage/morning summary |

### Notes
- `delegation`은 `physio-orchestrator`에만 우선 허용 추천
- `cronjob`은 `physio-ops-reporter` 위주, 다른 프로필은 최소화
- `browser`는 `frontend`, `qa`, `designer`에 우선
- `code_execution`은 `backend`에 우선

---

## 5. Per-Profile Spec

## 5.1 `physio-orchestrator` / 오케스트레이터
**Mission:** 전체 agent 흐름 조율, kanban/task routing, nightly 진입 조건 판단  
**Primary toolsets:** `file, terminal, skills, todo, session_search, messaging`  
**Optional:** `delegation`  
**Should avoid:** 대규모 코드 구현  
**Best for:** task graph, assignee routing, morning decision, blocked 해소

### Recommended behavior
- 직접 고치기보다 배정/정리/요약에 집중
- READY 품질과 lane balance를 KPI로 본다

## 5.2 `physio-planner` / 기획자
**Mission:** 요구사항→실행 스펙 변환  
**Primary toolsets:** `file, search, session_search, todo, skills`  
**Should avoid:** 구현까지 과하게 넘보기  
**Best for:** PRD 초안, acceptance criteria, verify command draft

## 5.3 `physio-frontend` / 프론트엔드
**Mission:** 화면/상호작용/UI polish 구현  
**Primary toolsets:** `file, terminal, browser, vision, skills`  
**Should avoid:** 서버/인프라 깊은 수정  
**Best for:** page/component/form/UX fix

## 5.4 `physio-backend` / 백엔드
**Mission:** 서버 로직/API/tool runtime 구현  
**Primary toolsets:** `file, terminal, code_execution, skills`  
**Should avoid:** DB schema/RLS/auth/billing/CI를 가볍게 건드리기  
**Best for:** server actions, domain logic, agent runtime, data transforms

## 5.5 `physio-qa` / 검증자
**Mission:** verify/smoke/regression 책임  
**Primary toolsets:** `file, terminal, browser, vision, skills`  
**Should avoid:** 테스트 완화, skip 남발  
**Best for:** jest/eslint/typecheck/browser smoke, repro logs

## 5.6 `physio-designer` / 디자이너
**Mission:** UX 구조, 카피, 화면 질감 개선  
**Primary toolsets:** `file, browser, vision, image_gen, skills`  
**Should avoid:** 구현 난이도 무시한 과설계  
**Best for:** IA, microcopy, layout suggestions, landing polish

## 5.7 `physio-marketing` / 마케팅
**Mission:** 외부 커뮤니케이션과 소개 문구  
**Primary toolsets:** `file, web, search, skills, tts`  
**Should avoid:** 기능 이상 과장  
**Best for:** X thread, release note, landing copy, value prop

## 5.8 `physio-ops-reporter` / 운영리포터
**Mission:** morning report, lineage, run summary  
**Primary toolsets:** `file, terminal, session_search, cronjob, messaging, skills`  
**Should avoid:** 제품 코드 수정  
**Best for:** 보고 자동화, 추세 요약, next-seed hint

---

## 6. Recommended Create Order

### Step 1
먼저 5개만 만든다.

```bash
hermes profile create physio-orchestrator --clone-from default
hermes profile create physio-planner --clone-from default
hermes profile create physio-frontend --clone-from default
hermes profile create physio-backend --clone-from default
hermes profile create physio-qa --clone-from default
```

### Step 2
각 프로필에 alias를 붙인다.

예시:
```bash
hermes profile alias physio-orchestrator add po
hermes profile alias physio-planner add pp
hermes profile alias physio-frontend add pf
hermes profile alias physio-backend add pb
hermes profile alias physio-qa add pq
```

### Step 3
toolsets를 role별로 줄인다.

원칙:
- 너무 많은 툴을 다 열지 말기
- 각 역할의 실패 비용이 큰 툴부터 제한하기

---

## 7. Profile-by-Profile Tool Restriction Draft

이건 즉시 자동 적용값이 아니라 **권장 spec**이다.

### physio-orchestrator
- keep: `file, terminal, skills, todo, session_search, messaging, delegation`
- remove candidate: `browser, image_gen, code_execution`

### physio-planner
- keep: `file, web, skills, todo, session_search`
- remove candidate: `terminal, browser, code_execution`

### physio-frontend
- keep: `file, terminal, browser, vision, skills`
- remove candidate: `cronjob, messaging`

### physio-backend
- keep: `file, terminal, code_execution, skills`
- remove candidate: `image_gen, browser, tts`

### physio-qa
- keep: `file, terminal, browser, vision, skills`
- remove candidate: `image_gen, messaging, cronjob`

### physio-designer
- keep: `file, browser, vision, image_gen, skills`
- remove candidate: `terminal, cronjob, code_execution`

### physio-marketing
- keep: `file, web, skills, tts`
- remove candidate: `terminal, code_execution, cronjob`

### physio-ops-reporter
- keep: `file, terminal, session_search, cronjob, messaging, skills`
- remove candidate: `browser, image_gen, code_execution`

---

## 8. Mapping to Existing physio_app Automation

현재 자산과 연결:
- `physio-orchestrator` → Kanban, READY, nightly wave 진입 판단
- `physio-planner` → `overnight_tasks.txt` READY 품질 정리
- `physio-frontend` / `physio-backend` → 실제 nightly 작업 수행 주체
- `physio-qa` → verify commands 실행 책임
- `physio-ops-reporter` → morning report + status card summary

즉 현재 자동화 구조를 버리는 게 아니라, **역할 이름을 붙여서 운영체계로 승격**하는 개념이다.

---

## 9. Immediate Next Steps

### Task 1
5개 core profile부터 실제 생성

### Task 2
각 profile의 `AGENTS.md` 또는 profile-specific persona 문구 정리

### Task 3
toolset 제한 실제 반영

### Task 4
nightly runbook에서 어떤 프로필이 어느 단계에 들어가는지 문서화

---

## 10. One-Line Recommendation

**지금은 `physio-orchestrator`, `physio-planner`, `physio-frontend`, `physio-backend`, `physio-qa` 5개만 먼저 실제로 만들고, `designer/marketing/ops-reporter`는 2차 확장으로 붙이는 게 가장 안전하고 효율적이다.**
