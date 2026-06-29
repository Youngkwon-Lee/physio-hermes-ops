# CONTINUITY_HANDOFF_RUNBOOK_V0_1

## Purpose

Use this when MacBook Codex App, desktop Hermes, Discord, or Mission Control needs to hand work to another surface.

The goal is not to save every chat message.

The goal is to preserve enough state for another agent to continue safely.

## Minimal Command

```bash
python3 scripts/capture_continuity_handoff.py --input handoff.json
```

Use a real second-brain directory:

```bash
SECOND_BRAIN_DIR=/home/yk/brain-linux \
python3 scripts/capture_continuity_handoff.py --input handoff.json
```

On the home desktop, `/home/yk/brain-linux` is the automation canonical checkout. `/home/yk/brain` is a legacy symlink to the Windows Obsidian mirror and should not be used as the default automation write path.

Local fallback writes to:

```text
ops_knowledge/
```

## Example Payload

```json
{
  "schema": "continuity_handoff_v0_1",
  "source": {
    "surface": "codex-app",
    "runId": "8367e044-4b4a-4735-8f61-f4d64c688882",
    "threadId": "1490291482479824957",
    "repo": "Youngkwon-Lee/physio-hermes-ops",
    "branch": "codex/agent-os-runtime-split"
  },
  "goal": "Codex bridge result is visible in Mission Control",
  "done": [
    "MacBook Codex smoke passed",
    "Mission Control accepts codex-bridge-result artifacts"
  ],
  "next": [
    "Add raw continuity handoff capture",
    "Create pending second-brain candidate"
  ],
  "blockers": [],
  "decisions": [
    {
      "summary": "Do not write directly to canonical memory",
      "reason": "Avoid context pollution",
      "owner": "operator"
    }
  ],
  "artifacts": [
    {
      "label": "Mission Control run",
      "kind": "run",
      "url": "http://127.0.0.1:3005/mission-control"
    }
  ],
  "memoryCandidates": [
    {
      "title": "Use raw before canonical memory",
      "type": "rule",
      "summary": "Agent runs should create immutable raw handoff first, then pending candidates, before canonical promotion.",
      "whyItMatters": "This prevents unverified run output from becoming durable operating memory.",
      "proposedDestination": "operations/agent-os/memory-policy.md",
      "confidence": 0.9
    }
  ]
}
```

## Output

Raw:

```text
operations/raw/continuity/YYYY-MM-DD/*.json
operations/raw/continuity/YYYY-MM-DD/*.md
```

Candidate:

```text
operations/candidates/continuity/YYYY-MM-DD/*.md
```

Event:

```text
operations/events/continuity_handoff_events.jsonl
```

## Desktop Hermes Notification

Default mode writes a JSONL event that desktop Hermes can poll or watch.

```bash
python3 scripts/capture_continuity_handoff.py \
  --input handoff.json \
  --event-log /home/yk/brain-linux/operations/events/continuity_handoff_events.jsonl
```

Near real-time mode sends the same event to a running Hermes/Mission Control API.

```bash
CONTINUITY_HANDOFF_NOTIFY_URL=http://100.83.147.56:8792/handoff/notify \
CONTINUITY_HANDOFF_NOTIFY_TOKEN="$MISSION_CONTROL_SHARED_TOKEN" \
python3 scripts/capture_continuity_handoff.py --input handoff.json
```

The sender now includes both auth headers:

- `Authorization: Bearer <token>`
- `x-hermes-api-key: <token>`

The receiving API stores notifications at:

```text
lineage/continuity_handoff_notifications.jsonl
```

Use JSONL first. Turn on HTTP notification only after the desktop API address and token are confirmed.

## MacBook Canonical Env

Until the direct WSL path is made reliable again, use the Windows host path as the default external smoke route.

```bash
export MISSION_CONTROL_BASE_URL="http://100.83.147.56:8792"
export MISSION_CONTROL_SHARED_TOKEN="<shared-token>"
export CONTINUITY_HANDOFF_NOTIFY_URL="http://100.83.147.56:8792/handoff/notify"
export CONTINUITY_HANDOFF_NOTIFY_TOKEN="$MISSION_CONTROL_SHARED_TOKEN"
```

These work for:

- `scripts/continuity_handoff_notify_smoke.py`
- `scripts/capture_continuity_handoff.py`

Compatibility env still supported:

- `HERMES_DESKTOP_MISSION_CONTROL_URL`
- `HERMES_MISSION_CONTROL_API_KEY`

## MacBook Codex <-> desktop Hermes Operating Loop

Use this loop when MacBook Codex needs desktop Hermes to act, verify, or report back without the user manually copying state between surfaces.

Canonical surfaces:

- live discussion: Discord `#second_memory / 맥북코덱스소통채널`
- durable state: Mission Control `/handoffs`
- code history: GitHub `main` or a named branch
- live verification: MacBook direct API checks against `http://100.83.147.56:8792`
- durable rationale: second memory, only when the result is worth keeping

Do not use unrelated domain threads such as `방문재활 일정 관리` for MacBook/Hermes coordination unless the operator explicitly selects them.

### 1) Create a Mission Control handoff

From MacBook:

```bash
curl -sS -X POST "$MISSION_CONTROL_BASE_URL/handoffs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN" \
  -d @- <<'JSON'
{
  "organizationId": "org-smoke",
  "from": {"agent": "macbook-codex", "surface": "codex-app", "host": "macbook"},
  "to": {"agent": "desktop-hermes", "surface": "discord", "host": "desktop"},
  "repo": "/home/yk/physio-hermes-ops",
  "goal": "Pull the pushed main commit, restart ops-control-api.service, and verify live health.",
  "context": "MacBook Codex pushed a change that desktop Hermes must apply on the live service.",
  "expectedOutput": "Reply with HEAD, service status, /health fields, and /handoffs smoke result.",
  "sourceThread": {"channelName": "second_memory", "threadName": "맥북코덱스소통채널"},
  "status": "waiting_for_codex",
  "tags": ["macbook-codex", "desktop-hermes", "mission-control"]
}
JSON
```

Record the returned `handoff-...` id.

### 2) Notify the Discord thread

Post a bounded instruction to `#second_memory / 맥북코덱스소통채널` after the operator approves the exact message or a clearly bounded summary.

Include:

- `[FROM: macbook-codex] [TO: desktop-hermes]`
- the repo path
- the target commit or branch
- the exact command-level intent
- expected evidence
- the Mission Control handoff id

If desktop Hermes replies before a draft is sent, delete the stale draft instead of sending it.

### 3) Verify from MacBook

After desktop replies, verify live state directly from MacBook:

```bash
curl -sS --max-time 8 "$MISSION_CONTROL_BASE_URL/health"
curl -sS --max-time 8 "$MISSION_CONTROL_BASE_URL/handoffs?organizationId=org-smoke&limit=5" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN"
```

For the stable handoff inbox fix, the expected `/health` fields are:

```text
handoff_inbox: /home/yk/.local/state/physio-hermes-ops/mission_control/handoff_inbox.json
handoff_inbox_legacy: /home/yk/physio-hermes-ops/.runtime/mission_control/handoff_inbox.json
```

### 4) Close the handoff

Only close the handoff after MacBook verification succeeds.

```bash
curl -sS -X POST "$MISSION_CONTROL_BASE_URL/handoffs/<handoff-id>/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MISSION_CONTROL_SHARED_TOKEN" \
  -d @- <<'JSON'
{
  "organizationId": "org-smoke",
  "status": "done",
  "result": "MacBook verified live /health and /handoffs after desktop Hermes applied the requested change."
}
JSON
```

Use `blocked` instead of `done` when desktop cannot apply the change, and include the concrete blocker in `result`.

### Verified June 14, 2026 closeout

- MacBook pushed `e26d5a5` to `origin/main`.
- desktop Hermes pulled `main`, restarted `ops-control-api.service`, and reported active/running.
- MacBook verified `http://100.83.147.56:8792/health`.
- `/health` showed stable `handoff_inbox` under `/home/yk/.local/state/...`.
- `/health` also exposed `handoff_inbox_legacy` under the canonical repo `.runtime` path.
- Mission Control handoff `handoff-73664534-3a56-480e-9ea2-5b2870f9921e` was marked `done` after MacBook verification.

## Desktop Smoke

Start the receiver on the desktop Hermes host:

```bash
cd /home/yk/physio-hermes-ops
git pull
HERMES_MISSION_CONTROL_HOST=0.0.0.0 \
HERMES_MISSION_CONTROL_PORT=8792 \
HERMES_MISSION_CONTROL_API_KEY="$MISSION_CONTROL_SHARED_TOKEN" \
python3 apps/api/mission_control_api.py
```

Then run this from MacBook:

```bash
python3 scripts/continuity_handoff_notify_smoke.py \
  --base-url http://100.83.147.56:8792 \
  --token "$MISSION_CONTROL_SHARED_TOKEN"
```

Expected result:

```text
"ok": true
```

If `8791` returns `404 page not found`, another service is using that port. Use `8792` for Mission Control API.

## Delayed Callback Smoke

Use this when you want to verify the full loop:

```text
MacBook -> desktop /handoff/notify -> desktop delayed callback -> MacBook receiver
```

First start a callback receiver on MacBook and keep it alive for at least 3 minutes.

```bash
python3 scripts/continuity_callback_capture_server.py \
  --host 0.0.0.0 \
  --port 8891 \
  --output /tmp/continuity_callback_capture.json
```

Then find the current MacBook Tailscale IPv4 address:

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4
```

Then run the direct desktop Tailscale smoke from MacBook:

```bash
python3 scripts/continuity_handoff_notify_smoke.py \
  --base-url http://100.125.26.99:8792 \
  --token "$MISSION_CONTROL_SHARED_TOKEN" \
  --callback-url http://<macbook-ip>:8891/ack \
  --surface macbook-codex \
  --run-id cross-device-callback-smoke-2 \
  --goal "Verify MacBook -> desktop continuity handoff plus delayed callback reply" \
  --verbose
```

Notes:

- The callback is not the immediate `POST /handoff/notify` response.
- Desktop sends the callback later through the `continuity-handoff-notifier` cron path.
- Do not stop the MacBook callback receiver immediately after the smoke command returns.

Success criteria:

- `scripts/continuity_handoff_notify_smoke.py` returns `"ok": true`
- `/tmp/continuity_callback_capture.json` is created on MacBook
- the callback payload includes:
  - `kind: "continuity_handoff_ack"`
  - `status: "ack"`
  - `runId: "cross-device-callback-smoke-2"`

Verified on June 13, 2026:

- direct desktop path `http://100.125.26.99:8792` returned `GET /health -> 200`
- `POST /handoff/notify -> 200`
- delayed callback reached the MacBook receiver at `/ack`

## June 13, 2026 Incident Note

- Symptom: MacBook smoke reached `GET /health` but failed `POST /handoff/notify` with `401 unauthorized`.
- Verified good path: `http://100.83.147.56:8792`.
- Direct WSL path `http://100.125.26.99:8792` remained unstable from MacBook during this incident.
- Root cause: MacBook scripts sent only `x-hermes-api-key`, while the active receiver path accepted `Authorization: Bearer`.
- Fix: send both `Authorization: Bearer` and `x-hermes-api-key` from the MacBook continuity scripts.
- Result: MacBook smoke returned `"ok": true`.
- Follow-up verification: delayed callback smoke later succeeded end-to-end with `http://100.125.26.99:8792` plus a live MacBook callback receiver.

## Stop Rules

Do not promote canonical memory automatically.

Do not store secrets, tokens, PHI, or private raw dumps.

Do not create a candidate when the note is one-off, uncertain, or not useful for handoff.

## Next Integration

1. Mission Control run completes.
2. Hermes creates a continuity handoff payload.
3. `capture_continuity_handoff.py` writes raw and candidate notes.
4. Mission Control shows pending candidates.
5. Human approves promotion into second-brain canonical wiki.
