# HEARTBEAT_RUNTIME_POLICY

문서 목적: 현재 physio-hermes-ops에 남아 있는 legacy heartbeat 산출물과, 앞으로 Hermes 중심 운영에서 사용할 **live heartbeat truth**를 분리해 정의한다.

## 현재 진단
2026-06-01 기준 점검 결과:
- Hermes cron scheduler 자체는 정상 작동 중이다.
- 그러나 `lineage/heartbeat.json`, `lineage/ralph_loop_state.json`, `dashboard/derived/ops_snapshot.json`의 heartbeat 필드는 **실시간 운영 truth로 보기 어렵다**.
- 이유:
  - heartbeat 관련 파일의 내용 시각이 `2026-05-13` 수준에 머물러 있음
  - 현재 Hermes active cron 목록에는 heartbeat를 갱신하는 job이 없음
  - 즉 대시보드가 보는 heartbeat와 현재 Hermes 런타임이 직접 연결돼 있지 않음

## 운영 판단
앞으로는 heartbeat를 두 층으로 나눈다.

### 1. Live runtime truth
Hermes 현재 운영 상태를 판정하는 1차 truth:
- `hermes cron status`
- `hermes cron list`
- 최근 cron output artifact (`~/.hermes/cron/output/...`)
- gateway log / errors log
- 필요 시 `hermes memory status`

이 층은 **실제 지금 살아 있는 시스템**을 반영한다.

### 2. Legacy ops lineage
기존 physio lineage 기반 heartbeat 관련 파일:
- `lineage/heartbeat.json`
- `lineage/ralph_loop_state.json`
- `dashboard/derived/ops_snapshot.json` 내부 heartbeat

이 층은 당분간 **historical / compatibility artifact**로 취급한다.

## 규칙
### Rule A — stale heartbeat는 healthy 신호로 쓰지 않는다
다음 조건 중 하나라도 만족하면 live heartbeat로 간주하지 않는다.
- 최근 갱신 시각이 기대 주기보다 충분히 오래됨
- 이를 갱신하는 Hermes cron job이 현재 active list에 없음
- artifact만 존재하고, runtime scheduler/log와 연결 근거가 없음

### Rule B — health 판단은 scheduler-first
운영 health 1차 판정 순서:
1. gateway / scheduler alive?
2. expected cron jobs running?
3. latest output fresh?
4. logs clean enough?
5. memory writable?
6. 그 다음에만 heartbeat snapshot 참고

### Rule C — dashboard는 stale 표시를 지원해야 한다
UI에서 heartbeat를 계속 노출한다면 다음 필드를 함께 보여야 한다.
- `generated_at`
- freshness 판정 (`fresh` / `stale` / `unknown`)
- source (`legacy-lineage` / `hermes-runtime`)

## 권장 재설계
두 가지 경로 중 하나를 택한다.

### Option 1 — Hermes-native heartbeat로 재구축 (권장)
새 heartbeat는 Hermes가 직접 관리한다.

권장 형태:
- job name 예시: `runtime-heartbeat-check`
- schedule 예시: `every 5m`
- deliver: `local`
- no_agent: `true` 또는 얇은 Python script
- output:
  - 최근 due job freshness
  - gateway/scheduler 상태
  - 마지막 성공 run 시각
  - health summary JSON/MD

산출물 예시:
- `~/.hermes/cron/output/<job_id>/...`
- 필요 시 public-safe projection만 `physio-hermes-ops/dashboard/derived/`로 export

### Option 2 — Legacy lineage heartbeat를 명시적으로 퇴역
Hermes-native health check를 heartbeat 대체물로 사용하고,
기존 `lineage/heartbeat.json`은 다음처럼 취급한다.
- archived
- deprecated
- dashboard에서 배지/경고 표시

## 최소 운영 기준 (MVP)
heartbeat가 "정상"이라고 말하려면 최소 다음을 만족해야 한다.
- scheduler running
- 최근 10분 내 watchdog/no_agent cron output 존재
- critical jobs의 `last_status != error`
- freshness source가 명시됨
- stale artifact를 healthy처럼 표시하지 않음

## 다음 실행 순서
1. built-in memory 여유 확보
2. 본 문서 기준으로 stale heartbeat 해석 중단
3. Hermes-native heartbeat check script 또는 cron 설계
4. dashboard에서 `source + freshness` 함께 표기
5. cron/heartbeat/memory 통합 health check로 확장

## 권장 문구
- "heartbeat alive" 대신
  - `runtime health: fresh`
  - `runtime health: stale lineage signal`
  - `scheduler alive, legacy heartbeat stale`
처럼 truth source를 같이 적는다.
