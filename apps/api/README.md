# apps/api

Mission Control API entrypoint.

This app should expose the typed interface consumed by product UIs such as `physio_app`.

## Current MVP

Run:

```bash
python3 apps/api/mission_control_api.py
```

Default bind:

- `http://127.0.0.1:8791`

Optional env:

- `HERMES_MISSION_CONTROL_HOST`
- `HERMES_MISSION_CONTROL_PORT`
- `HERMES_MISSION_CONTROL_API_KEY`
- `HERMES_MISSION_CONTROL_STATE_PATH`
- `HERMES_MISSION_CONTROL_EVENT_LOG`

GitHub publish env:

- `AGENT_OS_GITHUB_REPO` or `GITHUB_REPOSITORY`
- `AGENT_OS_GITHUB_TOKEN` or `GITHUB_TOKEN` or `GH_TOKEN`
- `AGENT_OS_GITHUB_CREATE_ISSUES=1`
- `AGENT_OS_GITHUB_CREATE_PULL_REQUEST=1`
- `AGENT_OS_GITHUB_BOOTSTRAP_BRANCH=1`
- optional: `AGENT_OS_GITHUB_APPLY_LABELS=1`

State is file-backed for now:

- runtime state: `.runtime/mission_control/state.json`
- append-only events: `lineage/mission_control_events.jsonl`

`POST /runs` optional source context:

- `source.streamId`
- `source.channelId`
- `source.threadId`
- `source.channelName`
- `source.threadName`

Use these when a run starts from a specific chat thread, operator channel, or reporting stream.

Auth:

- when `HERMES_MISSION_CONTROL_API_KEY` is set, send it as `x-hermes-api-key`
- `Authorization: Bearer <key>` also works for manual curl checks

## Planned responsibilities

- `GET /runs`
- `POST /runs`
- `POST /runs/:id/approve`
- `POST /runs/:id/reject`
- `POST /daily-ops`
- `POST /heartbeat/check`
- `GET /heartbeat/control`
- `GET /readiness`
- `POST /readiness/check`
- `POST /heartbeat/cron-request`
- `GET /snapshot`

## Snapshot shape

`GET /snapshot` should return:

- runs
- readiness
- heartbeatControl

This gives product UIs a single initial Mission Control hydration payload.

## Notes

- Keep this app thin.
- It should gradually delegate more logic to `packages/runtime`, `packages/workflows`, and `packages/connectors`.
- It should not own Physio-specific UI or route logic.
- When the GitHub env is missing, issue and PR publish stays in dry-run and records the reason in Mission Control artifacts and traces.
- Codex worker execution is outside this API for now. Validate the worker host with `python3 scripts/codex_remote_smoke.py --host macbook` before wiring execution into Mission Control runs.
