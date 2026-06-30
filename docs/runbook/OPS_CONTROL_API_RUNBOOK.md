# OPS Control API Runbook

## 1) 목적
Nautilus 대시보드에서 cron 운영 액션(refresh/pause/resume/finalize)을 안전하게 실행한다.

## 2) 보안 정책
- 기본값: `OPS_CTL_REQUIRE_TOKEN=1` (토큰 필수)
- READ/EXEC 분리:
  - `OPS_CTL_READ_TOKEN`: 히스토리 조회(`/actions/recent`) 전용
  - EXEC는 아래 중 하나
    - 단일: `OPS_CTL_EXEC_TOKEN`
    - 역할 분리(권장): `OPS_CTL_EXEC_ADMIN_TOKEN`, `OPS_CTL_EXEC_OPERATOR_TOKEN`
- 역할별 allowlist:
  - `admin`: 모든 액션 (`refresh`, `pause_all`, `resume_core`, `finalize_once`)
  - `operator`: `refresh`만 허용
- 토큰은 커밋 금지, 로컬 env 파일로만 주입
- 대시보드 localStorage 키:
  - `opsCtlReadToken`
  - `opsCtlExecAdminToken`
  - `opsCtlExecOperatorToken`
  - `opsCtlExecRoleMode` (`admin|operator`)

## 3) 로컬 실행
```bash
cd ~/physio-hermes-ops
export OPS_CTL_REQUIRE_TOKEN=1
export OPS_CTL_READ_TOKEN='READ_LONG_RANDOM_TOKEN'
export OPS_CTL_EXEC_ADMIN_TOKEN='EXEC_ADMIN_LONG_RANDOM_TOKEN'
export OPS_CTL_EXEC_OPERATOR_TOKEN='EXEC_OPERATOR_LONG_RANDOM_TOKEN'
# 선택: temp worktree와 canonical repo 사이에서 handoff 상태를 공유
export OPS_CTL_STATE_DIR="$HOME/.local/state/physio-hermes-ops/mission_control"
python3 scripts/ops_control_api.py
```

## 4) systemd(user) 등록
```bash
mkdir -p ~/.config/systemd/user ~/.config/physio-hermes-ops
cp deploy/systemd/ops-control-api.service ~/.config/systemd/user/
cp deploy/systemd/ops-control-api.env.example ~/.config/physio-hermes-ops/ops-control-api.env
# env 파일에서 토큰 값 교체
systemctl --user daemon-reload
systemctl --user enable --now ops-control-api.service
systemctl --user status ops-control-api.service --no-pager
```

## 5) 검증
```bash
# health (무인증)
curl -s http://127.0.0.1:8788/health

# recent (READ 토큰 필요)
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" \
  http://127.0.0.1:8788/actions/recent

# action dry-run (OPERATOR: refresh 허용)
curl -s -X POST http://127.0.0.1:8788/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_OPERATOR_TOKEN" \
  -d '{"action":"refresh","dry_run":true}'

# action dry-run (OPERATOR: pause_all 차단, 403)
curl -s -X POST http://127.0.0.1:8788/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_OPERATOR_TOKEN" \
  -d '{"action":"pause_all","dry_run":true}'

# action dry-run (ADMIN: pause_all 허용)
curl -s -X POST http://127.0.0.1:8788/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_ADMIN_TOKEN" \
  -d '{"action":"pause_all","dry_run":true}'
```

## 6) 감사로그/락
- 감사로그: `lineage/actions_audit.jsonl`
- 실행락: `.runtime/ops_control.lock`
- 동시 실행 요청 시 HTTP `409 busy` 반환

## 6-1) Mission Control handoff inbox
- 기본 저장 경로: `~/.local/state/physio-hermes-ops/mission_control/handoff_inbox.json`
- override:
  - `OPS_CTL_STATE_DIR`
  - `OPS_CTL_HANDOFF_INBOX_PATH`
  - 호환 env: `HERMES_MISSION_CONTROL_STATE_DIR`, `HERMES_MISSION_CONTROL_HANDOFF_INBOX_PATH`
- legacy repo-local 경로: `.runtime/mission_control/handoff_inbox.json`
- stable inbox가 없고 legacy 파일이 있으면 첫 load 때 stable 경로로 자동 복사된다.
- `/health`에서 `handoff_inbox`와 `handoff_inbox_legacy`를 확인한다.

## 6-2) Ops Knowledge (신규)
- 자동 지식화 저장 경로: `ops_knowledge/`
  - raw: `ops_knowledge/00_raw/YYYY-MM-DD/*.md`
  - wiki: `ops_knowledge/10_wiki/decisions/*.md`
- 액션 성공 시 lineage 스냅샷 자동 저장
- 수동 주입 API: `POST /knowledge/inject`
- 조회 API:
  - `GET /knowledge/recent`
  - `GET /knowledge/graph`

## 6-3) Mission Control action worker
목적: MacBook Codex가 GitHub에 push한 뒤 사람이 Discord/복붙으로 desktop `pull + restart + smoke`를 중계하지 않도록 한다.

흐름:
- MacBook Codex: `POST /mission-actions`로 bounded action 생성
- desktop worker: `/mission-actions/next` 조회
- desktop worker: `/mission-actions/<id>/claim` 후 허용된 action만 실행
- desktop worker: `/mission-actions/<id>/status`에 `done|failed|blocked`와 smoke 결과 기록
- MacBook Codex: `/mission-actions`와 live endpoint를 검증하고 handoff를 닫음

현재 허용 action type:
- `desktop_repo_sync_restart_smoke`: canonical repo에서 `git pull --ff-only`, `ops-control-api.service` restart, smoke endpoint 검증
- `desktop_hermes_prompt`: desktop worker가 로컬 `hermes -z`로 bounded prompt를 실행하고 결과를 action status에 기록

systemd(user) worker 활성화:
```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/mission-control-action-worker.service ~/.config/systemd/user/
cp deploy/systemd/mission-control-action-worker.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mission-control-action-worker.timer
systemctl --user list-timers mission-control-action-worker.timer --no-pager
```

MacBook에서 desktop deploy action 생성:
```bash
python3 scripts/create_desktop_deploy_action.py \
  --base-url http://100.83.147.56:8792 \
  --token "$MISSION_CONTROL_SHARED_TOKEN"
```

이 스크립트는 `/mission-actions`가 live이면 action을 만들고, 아직 old code라 `404`이면 bootstrap handoff와 `/handoff/notify`로 자동 fallback한다.

Raw API 예시:
```bash
curl -sS -X POST http://100.83.147.56:8792/mission-actions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN" \
  -d '{
    "organizationId": "org-smoke",
    "actionType": "desktop_repo_sync_restart_smoke",
    "title": "Deploy latest physio-hermes-ops main to desktop live",
    "target": {"agent": "desktop-hermes", "surface": "hermes-gateway", "host": "desktop-wsl"},
    "repo": "Youngkwon-Lee/physio-hermes-ops",
    "priority": 10,
    "params": {
      "repoPath": "/home/yk/physio-hermes-ops",
      "remote": "origin",
      "branch": "main",
      "serviceName": "ops-control-api.service",
      "smokeBaseUrl": "http://127.0.0.1:8792",
      "smokePaths": [
        "/health",
        "/plans?organizationId=org-smoke",
        "/tasks?organizationId=org-smoke",
        "/tasks/next?organizationId=org-smoke",
        "/snapshot?organizationId=org-smoke",
        "/mission-actions?organizationId=org-smoke&limit=1"
      ]
    }
  }'
```

상태 확인:
```bash
curl -sS "http://100.83.147.56:8792/mission-actions?organizationId=org-smoke&limit=5" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN"

curl -sS "http://100.83.147.56:8792/mission-actions/<action-id>?organizationId=org-smoke" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN"
```

Desktop Hermes prompt action 예시:
```bash
curl -sS -X POST http://100.83.147.56:8792/mission-actions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN" \
  -d '{
    "organizationId": "org-smoke",
    "actionType": "desktop_hermes_prompt",
    "title": "Ask desktop Hermes to summarize runtime status",
    "target": {"agent": "desktop-hermes", "surface": "hermes-gateway", "host": "desktop-wsl"},
    "priority": 20,
    "params": {
      "cwd": "/home/yk/physio-hermes-ops",
      "timeoutSec": 600,
      "prompt": "현재 desktop Hermes 상태를 5줄 이내로 요약하고 다음 조치 1개를 제안해."
    },
    "sourceThread": {
      "channelName": "second_memory",
      "threadName": "맥북코덱스소통채널",
      "threadId": "1515296585410416931"
    }
  }'
```

## 6-4) Discord/Hermes 회의 요약 -> Mission Control
목적: Discord/Hermes 회의에서 나온 결론을 prose-only 메시지로 흘려보내지 않고, Mission Control `/plans`와 `/tasks`에 구조화해 다음 작업으로 보이게 한다.

권장 입력은 bounded JSON이다:
```json
{
  "title": "회의에서 합의한 큰 목표",
  "summary": "결정 배경과 범위",
  "horizon": "short",
  "sourceThread": {
    "channelName": "second_memory",
    "threadName": "맥북코덱스소통채널",
    "threadId": "1515296585410416931"
  },
  "tasks": [
    {
      "title": "다음 실행 작업",
      "context": "왜 필요한지",
      "expectedOutput": "완료 기준",
      "assignee": {"agent": "desktop-hermes", "surface": "discord", "host": "desktop-wsl"},
      "priority": 10
    }
  ]
}
```

Hermes/desktop에서 ingest:
```bash
python3 scripts/ingest_discord_meeting_to_mission_control.py \
  --base-url http://127.0.0.1:8792 \
  --token "$MISSION_CONTROL_SHARED_TOKEN" \
  --input meeting_summary.json
```

MacBook에서 외부 검증:
```bash
curl -sS "http://100.83.147.56:8792/tasks/next?organizationId=org-smoke" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN"
```

### 6-5) Discord thread -> ingest trigger
목적: `#second_memory / 맥북코덱스소통채널`에 Hermes가 남긴 bounded meeting payload를 사람이 다시 복사하지 않고 Mission Control로 넣는다.

Discord 메시지 형식은 fence 또는 marker를 사용한다:
````markdown
```mission-control-json
{
  "title": "회의에서 합의한 큰 목표",
  "summary": "결정 배경과 범위",
  "tasks": [
    {
      "title": "다음 실행 작업",
      "context": "왜 필요한지",
      "expectedOutput": "완료 기준"
    }
  ]
}
```
````

desktop/Hermes에서 thread 최신 메시지 ingest:
```bash
HERMES_DISCORD_BOT_TOKEN="$HERMES_DISCORD_BOT_TOKEN" \
python3 scripts/ingest_discord_thread_to_mission_control.py \
  --base-url http://127.0.0.1:8792 \
  --token "$MISSION_CONTROL_SHARED_TOKEN" \
  --thread-id 1515296585410416931
```

Kinelo Ops 운영 인박스 미러링:
```bash
export KINELO_OPS_INTAKE_URL="https://kinelo-ops.vercel.app/api/ops-intake"
export KINELO_OPS_INTAKE_SECRET="<server-only-intake-secret>"
export KINELO_OPS_MIRROR_POLICY="important"
```

- env가 없으면 기존처럼 Mission Control에만 저장한다.
- 기본 정책은 `important`이며, 모든 Discord task를 무조건 Kinelo Ops로 보내지 않는다.
- `KINELO_OPS_MIRROR_POLICY=all`이면 모든 `tasks[]`를 미러링하고, `off`이면 미러링을 끈다.
- `important` 정책에서는 아래 중 하나일 때만 Kinelo Ops `tasks`에 `source_provider=discord`로 생성한다.
- 명시 플래그: `kineloOps`, `kinelo_ops`, `opsTask`, `mirrorToKineloOps`, `mirror_to_kinelo_ops`가 true.
- 태그/본문 키워드: `important`, `urgent`, `action`, `handoff`, `ops`, `automation`, `business`, `customer`, `revenue`, `decision`, `follow-up`, `중요`, `긴급`, `실행`, `후속`, `운영`, `자동화`, `사업`, `고객`, `매출`, `결정`.
- 우선순위: Mission Control task `priority <= 30`.
- 중복 키는 `discord-thread:<thread-id>:<message-id>:<task-index>`이며, Kinelo Ops가 같은 요청을 dedupe한다.
- `DISCORD_GUILD_ID`가 있으면 source URL은 `https://discord.com/channels/<guild>/<thread>/<message>` 형태로 저장한다.

토큰 없이 fixture smoke:
```bash
python3 scripts/ingest_discord_thread_to_mission_control.py \
  --messages-json /tmp/discord-meeting-messages.json \
  --dry-run
```

중복 방지 state:
```text
~/.local/state/physio-hermes-ops/mission_control/discord_thread_ingest_state.json
```

desktop timer 설치:
```bash
cp deploy/systemd/mission-control-discord-thread-ingest.service ~/.config/systemd/user/
cp deploy/systemd/mission-control-discord-thread-ingest.timer ~/.config/systemd/user/

# ~/.config/physio-hermes-ops/ops-control-api.env 에 HERMES_DISCORD_BOT_TOKEN 설정 필요
systemctl --user daemon-reload
systemctl --user enable --now mission-control-discord-thread-ingest.timer
systemctl --user list-timers mission-control-discord-thread-ingest.timer --no-pager
```

## 7) 토큰 회전(rotate)
```bash
# 1) 새 토큰 생성
python3 - <<'PY'
import secrets
print('OPS_CTL_READ_TOKEN=' + secrets.token_urlsafe(32))
print('OPS_CTL_EXEC_ADMIN_TOKEN=' + secrets.token_urlsafe(32))
print('OPS_CTL_EXEC_OPERATOR_TOKEN=' + secrets.token_urlsafe(32))
PY

# 2) ~/.config/physio-hermes-ops/ops-control-api.env 교체 저장
# 3) 서비스 재시작
systemctl --user restart ops-control-api.service

# 4) 새 토큰으로 API 검증
```
브라우저에서는 `READ 토큰 설정`, `EXEC ADMIN 토큰 설정`, `EXEC OPERATOR 토큰 설정` 후
`exec role`을 선택해서 즉시 반영.

## 8) 트러블슈팅
- `401 unauthorized (scope=read|exec)`: 해당 scope 토큰 누락/불일치
- `403 forbidden_action`: 현재 exec role에서 허용되지 않은 액션
- `500 server_read_token_not_configured`: READ 토큰 미설정
- `500 server_exec_token_not_configured`: EXEC 토큰 미설정
- `500` with failed command: `actions_audit.jsonl` 및 응답 `results[].stderr` 확인
