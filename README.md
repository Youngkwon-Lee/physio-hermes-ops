# physio-hermes-ops

Hermes 멀티프로필 운영(physio-*)을 위한 공개 운영 레포입니다.

## 포함 범위 (MVP)
- 프로필 스펙/페르소나 문서
- nightly 운영 runbook/timeout 정책
- smoke rehearsal 산출물 샘플
- lineage 이벤트 로그(JSONL) + 집계 스크립트
- 정적 미니 대시보드(`dashboard/index.html`)

## 디렉토리
- `docs/architecture/` : 시스템 맵, delivery channel map, runtime split 등 구조 문서 (`HERMES_SYSTEM_MAP.md`, `PHYSIO_APP_RUNTIME_SPLIT.md` 포함)
- `docs/planning/` : 운영 문서 및 실험/로드맵 문서
- `docs/runbook/` : 실행/장애 대응 runbook (`CRON_OPERATIONS.md`, `HEARTBEAT_RUNTIME_POLICY.md`, `OPS_CONTROL_API_RUNBOOK.md` 등)
- `docs/specs/` : 브리핑 포맷 spec, lineage/event 스키마
- `docs/reports/` : 공개 가능한 샘플 리포트/산출물
- `docs/planning/smoke_sandbox/` : 스모크 리허설 샘플 아티팩트
- `cron/registry/` : public-safe cron job registry
- `cron/prompts/` : cron prompt 원본(향후 관리 대상)
- `cron/scripts/` : cron용 스크립트 원본(향후 관리 대상)
- `profiles/` : 프로필 템플릿/정책 문서(민감정보 제외)
- `automation/` : 스크립트 템플릿(민감정보 제외)
- `lineage/` : 실행 이벤트 로그(JSONL)
- `scripts/` : 집계/리포트/점검 스크립트 (`check_cron_registry.py` 포함)
- `dashboard/` : 정적 대시보드

## Codex worker smoke

MacBook Codex bundled CLI를 Hermes worker로 붙이기 전, transport/binary/exec/artifact만 검증한다.

- 설계: `docs/architecture/CODEX_BRIDGE_V0_1.md`
- runbook: `docs/runbook/MACBOOK_CODEX_REMOTE_WORKER_SMOKE_TEST_V0_1.md`
- script: `python3 scripts/codex_remote_smoke.py --host macbook`
- local health: `python3 scripts/codex_remote_smoke.py --local --health-only`
- if `Connection refused`, enable Remote Login on the MacBook before retrying

## Continuity handoff

MacBook Codex App, desktop Hermes, Discord, Mission Control이 서로 이어받을 수 있도록 raw/candidate handoff를 남긴다.

- 설계: `docs/architecture/CONTINUITY_HANDOFF_V0_1.md`
- schema: `docs/specs/continuity_handoff_schema_v0_1.json`
- runbook: `docs/runbook/CONTINUITY_HANDOFF_RUNBOOK_V0_1.md`
- script: `python3 scripts/capture_continuity_handoff.py --input handoff.json`

## dashboard read model 생성
- `python scripts/build_dashboard_read_models.py`
- 생성 위치: `dashboard/derived/`
- 산출물:
  - `rooms.json`
  - `seats.json`
  - `help_queue.json`
  - `showcase.json`
  - `ops_snapshot.json`
  - `feed.json`
  - `kpis.json`
  - `automation_health.json`
  - `runtime_health_snapshot.json`

이 파생 JSON은 `dashboard-v2` 같은 공간형 UI가 raw lineage 대신 읽는 1차 read model 용도다.

## runtime health snapshot
- `python scripts/write_runtime_health_snapshot.py`
- 생성 위치:
  - `dashboard/derived/runtime_health_snapshot.json`
  - `lineage/runtime_health_snapshot.md`
- 포함:
  - Hermes runtime health
  - Mission Control local API reachability
  - `physio_app` cron lane presence
  - automation health read model summary

## dashboard-v2 미리보기
- repo root에서 `python -m http.server 8787`
- 접속 경로: `http://localhost:8787/dashboard-v2/`
- `dashboard-v2`는 `dashboard/derived/*.json`을 읽는 공간형 운영 UI MVP다.

## Vercel 배포 (대시보드)
- `vercel.json` 기준으로 `/` → `dashboard/index.html` 라우팅
- API endpoint는 `dashboard/config.js`의 `window.NAUTILUS_CONFIG.opsApiBaseUrl`로 오버라이드 가능
- URL 파라미터 오버라이드도 지원: `?api=https://ops-api.example.com`
- 미설정 시 로컬 기본값(`http://127.0.0.1:8788`) 사용
- 외부 배포용 샘플은 `dashboard/config.example.js` 참고

### 빠른 배포 절차
1. Vercel에서 이 레포를 Import 후 배포
2. API를 외부에서 접근 가능한 endpoint로 준비(예: Tunnel/Reverse Proxy)
3. `dashboard/config.js`에서 `opsApiBaseUrl`을 외부 endpoint로 지정
4. 대시보드에서 READ/EXEC 토큰을 브라우저에 입력해 사용 (토큰 하드코딩 금지)

## 보안 원칙
- 토큰/키/개인정보는 커밋 금지
- `.env`, `*.key`, `*.pem`, `*.p12`, `*.gpg` 등은 기본 ignore
