# DASHBOARD_V2_SPATIAL_ARCHITECTURE_V0_1

> Goal: `physio-hermes-ops`의 기존 운영 코어를 유지한 채, `운영 콘솔 + 스터디카페형 공간 시각화`를 함께 제공하는 `dashboard-v2`를 설계한다.

**Decision:** 새로 갈아엎지 않는다.  
기존 `lineage/`, `scripts/`, `ops_control_api.py`는 운영 코어로 유지하고, `dashboard-v2`를 별도 UI 계층으로 증축한다.

**Primary Outcome:** 사용자는 한 화면에서
- 현재 에이전트 배치와 작업 상태를 공간적으로 보고
- 막힌 일(`CHECK`/`FAIL`)을 즉시 발견하고
- 필요하면 기존 Hermes 운영 액션(`refresh`, `resume_core`, `pause_all`, `finalize_once`)을 실행할 수 있다.

---

## 1. Core Principle

`dashboard-v2`는 아래 4계층으로 본다.

1. `Execution Layer`
- Hermes CLI
- cron jobs
- profile별 작업 실행

2. `Lineage Layer`
- `lineage/events.jsonl`
- `lineage/wave_queue.jsonl`
- `lineage/*_state.json`

3. `Read Model Layer`
- UI 전용 파생 JSON
- 공간 뷰, KPI, 도움 요청 큐, 쇼케이스 카드용 데이터

4. `Experience Layer`
- 스터디카페형 메인 UI
- 운영 디버그 drawer

핵심은 `UI가 raw JSONL을 직접 해석하지 않게 하는 것`이다.  
집계 규칙을 `read model`로 한번 굳히면 화면이 훨씬 단순해지고, 이후 저장소를 SQLite/Postgres로 바꿔도 UI를 거의 유지할 수 있다.

---

## 2. Keep / Replace / Later

## Keep
- `lineage` 이벤트 스키마
- `scripts/export_cron_status.py`
- `scripts/lineage_report.py`
- `scripts/ops_control_api.py`
- `profile_id`, `stream_id`, `wave_id`, `stage`, `status` 기반 모델

## Replace
- `dashboard/index.html` 단일 파일 UI를 메인 제품 UI로 쓰는 구조
- raw event를 브라우저에서 직접 광범위하게 가공하는 방식
- 운영 정보와 사용자형 공간 UI가 한 화면에서 같은 밀도로 섞인 구조

## Later
- JSONL에서 SQLite/Postgres로 이전
- 실시간 push
- 멀티 사용자 인증
- 이력 검색 고도화

---

## 3. Spatial Mapping

기존 이벤트 필드를 공간형 메타포로 맵핑한다.

| Source Field | Spatial Meaning | Notes |
|---|---|---|
| `profile_id` | 좌석에 앉은 에이전트 | 아바타/카드 단위 |
| `stream_id` | 방 또는 라운지 | `physio_bot`, `overnight`, `mem` 등 |
| `stage` | 작업 구역 | `plan`, `build`, `verify`, `report`, `dispatch` |
| `status` | 상태 조명 | `PASS=집중`, `CHECK=도움 필요`, `FAIL=막힘` |
| `wave_id` | 현재 라운드 | 오늘의 작업권, 세션 라벨 |
| `score` | 생산성/성과 | 카드 배지, 레벨 지표 |
| `retry_count` | 피로도/재시도 | 리스크 힌트 |
| `cost_tokens` | 리소스 사용량 | 운영 drawer에서 주로 표시 |
| `artifact_paths` | 결과물 흔적 | 쇼케이스 연결 |
| `links.commit`, `links.pr` | 실제 산출 링크 | 쇼케이스/히스토리 |

---

## 4. Information Architecture

첫 MVP는 5개 뷰로 제한한다.

## 4.1 Floor View
- 목적: 방별 혼잡도와 상태 파악
- 데이터: `rooms.json`
- UI:
  - 층/방 카드
  - active seat 수
  - `CHECK`/`FAIL` 카운트
  - 최근 wave 요약

## 4.2 Seat Map
- 목적: 현재 누가 어디서 무엇을 하는지 보기
- 데이터: `seats.json`
- UI:
  - 좌석 그리드
  - profile 카드
  - 상태 색상
  - 클릭 시 에이전트 상세 drawer

## 4.3 Help Desk
- 목적: 막힌 작업만 빠르게 보기
- 데이터: `help_queue.json`
- UI:
  - `CHECK`, `FAIL` 우선 정렬
  - 최근 1개 이벤트 요약
  - 담당 profile / stream / wave 표시

## 4.4 Showcase
- 목적: 결과물/PR/commit 가시화
- 데이터: `showcase.json`
- UI:
  - score 상위 이벤트
  - PR/commit/report 링크
  - profile별 최근 산출

## 4.5 Ops Drawer
- 목적: 운영자는 깊게 보고, 일반 사용자는 덜 방해받게 하기
- 데이터: `ops_snapshot.json`, `cron_status.json`
- UI:
  - FSM 상태
  - cron on/off
  - generation decision
  - action buttons

---

## 5. Read Model Contract

모든 파생 산출물은 `dashboard/derived/` 아래에 생성한다.

예상 구조:

```text
dashboard/
  derived/
    rooms.json
    seats.json
    help_queue.json
    showcase.json
    ops_snapshot.json
    feed.json
    kpis.json
```

### 공통 규칙
- 모든 파일은 `generated_at` 포함
- 모든 파일은 `source_window` 포함
- 타임스탬프는 ISO 8601 문자열
- 화면은 원칙적으로 `derived`만 읽고, `raw lineage`는 fallback/debug 용도로만 읽는다

---

## 6. Derived Schemas

## 6.1 `rooms.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "source_window": {
    "event_limit": 200,
    "latest_wave_id": "wave-17"
  },
  "items": [
    {
      "room_id": "plan-room",
      "name": "기획실",
      "stream_id": "physio_bot",
      "stage_group": "plan",
      "capacity": 4,
      "active_count": 1,
      "check_count": 0,
      "fail_count": 0,
      "dominant_status": "PASS",
      "profiles": ["physio-planner"],
      "latest_wave_id": "wave-17"
    }
  ]
}
```

## 6.2 `seats.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "items": [
    {
      "seat_id": "build-frontend-1",
      "room_id": "build-room",
      "profile_id": "physio-frontend",
      "display_name": "프론트엔드",
      "stream_id": "physio_bot",
      "stage": "build",
      "status": "PASS",
      "wave_id": "wave-17",
      "score": 88,
      "retry_count": 0,
      "cost_tokens": 4200,
      "summary": "UI polish 진행 중",
      "last_event_at": "2026-05-24T15:24:10+09:00",
      "links": {
        "commit": null,
        "pr": null,
        "report": null
      }
    }
  ]
}
```

## 6.3 `help_queue.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "items": [
    {
      "id": "evt-1024",
      "priority": "high",
      "status": "FAIL",
      "profile_id": "physio-backend",
      "stream_id": "overnight",
      "wave_id": "wave-17",
      "stage": "verify",
      "summary": "API smoke 실패",
      "retry_count": 2,
      "last_event_at": "2026-05-24T15:22:00+09:00",
      "artifact_paths": ["docs/reports/waves/dispatch_wave-17_task2.json"]
    }
  ]
}
```

## 6.4 `showcase.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "items": [
    {
      "id": "showcase-wave17-frontend",
      "profile_id": "physio-frontend",
      "wave_id": "wave-17",
      "score": 92,
      "title": "예약 페이지 인터랙션 개선",
      "summary": "form UX와 상태 전환을 정리",
      "links": {
        "commit": "https://github.com/example/repo/commit/123",
        "pr": "https://github.com/example/repo/pull/45",
        "report": null
      },
      "artifact_paths": ["docs/reports/waves/dispatch_wave-17_task1.json"],
      "published_at": "2026-05-24T15:10:00+09:00"
    }
  ]
}
```

## 6.5 `ops_snapshot.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "fsm": {
    "state": "RUNNING",
    "reason": "spawn/dispatch scheduled"
  },
  "generation": {
    "decision": "GREEN",
    "resume_recommendation": "RESUME"
  },
  "heartbeat": {
    "alive": true
  },
  "actions": [
    "refresh",
    "pause_all",
    "resume_core",
    "finalize_once"
  ]
}
```

## 6.6 `kpis.json`

```json
{
  "generated_at": "2026-05-24T15:30:00+09:00",
  "summary": {
    "active_profiles": 5,
    "active_streams": 3,
    "pass_count": 11,
    "check_count": 2,
    "fail_count": 1,
    "latest_wave_id": "wave-17",
    "avg_score": 84.1
  }
}
```

---

## 7. Build Rules

`derived` 생성 규칙은 단순해야 한다.

1. latest event 기준으로 `profile_id`별 현재 상태를 정한다.
2. `stage`를 room 그룹으로 매핑한다.
3. `CHECK`, `FAIL`만 help queue에 올린다.
4. `score`와 `links`가 있는 이벤트는 showcase 후보로 본다.
5. generation/FSM/heartbeat는 운영 snapshot에 모은다.

추천 room 매핑:

```text
plan      -> 기획실
build     -> 개발실
verify    -> QA룸
report    -> 운영실
dispatch  -> 배차실
```

추천 stream 표시:

```text
physio_bot -> 메인 작업방
overnight  -> 야간 자동화실
mem        -> 메모리/기록실
```

---

## 8. API Strategy

초기에는 `dashboard-v2`가 두 소스를 읽게 한다.

1. 정적 JSON
- `/derived/*.json`

2. 제어 API
- `ops_control_api.py`

읽기 경로와 실행 경로를 분리하면 운영 리스크가 줄어든다.

### Read
- `rooms.json`
- `seats.json`
- `help_queue.json`
- `showcase.json`
- `kpis.json`
- `ops_snapshot.json`
- `cron_status.json`

### Execute
- `POST /action`
- `refresh`
- `pause_all`
- `resume_core`
- `finalize_once`

---

## 9. UI Composition

메인 레이아웃은 아래를 권장한다.

```text
Topbar
  - 현재 wave
  - active profiles
  - 상태 pill

Main
  - Left: Floor View / Help Desk
  - Center: Seat Map
  - Right: Agent Detail Drawer or Showcase

Bottom or Slide-over
  - Ops Drawer
```

이렇게 두면 사용자는 먼저 공간과 상태를 보고, 운영자는 필요할 때만 깊은 패널을 연다.

---

## 10. Phased Delivery

## Phase 1
- `dashboard/derived` 생성 스크립트 추가
- 정적 JSON 계약 확정
- 기존 대시보드 병행 유지

## Phase 2
- `dashboard-v2` 첫 화면
- Floor View
- Seat Map
- Help Desk

## Phase 3
- Showcase
- Ops Drawer
- profile detail card

## Phase 4
- SQLite/Postgres read model 검토
- websocket 또는 polling 최적화

---

## 11. Immediate Next Files

다음 구현 때 가장 먼저 필요한 파일은 이 정도다.

- `scripts/build_dashboard_read_models.py`
- `dashboard/derived/*.json`
- `dashboard-v2/index.html` 또는 `dashboard-v2/app/*`
- `dashboard-v2/config.js`

---

## 12. Recommendation

`physio-hermes-ops`는 이미 `운영 엔진`이 있다.  
이번 v2의 목적은 엔진을 새로 만드는 것이 아니라, 그 엔진이 돌아가는 모습을 사람이 더 빨리 이해하고 개입할 수 있게 `공간형 인터페이스`로 번역하는 것이다.

즉, 이 프로젝트의 다음 좋은 움직임은:

- `backend rewrite`가 아니라
- `read model 추가`와
- `UI 계층 분리`다.
