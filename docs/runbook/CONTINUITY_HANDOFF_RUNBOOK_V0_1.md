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
SECOND_BRAIN_DIR=/home/yk/brain \
python3 scripts/capture_continuity_handoff.py --input handoff.json
```

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
  --event-log /home/yk/brain/operations/events/continuity_handoff_events.jsonl
```

Near real-time mode sends the same event to a running Hermes/Mission Control API.

```bash
CONTINUITY_HANDOFF_NOTIFY_URL=http://DESKTOP_HOST:8791/handoff/notify \
CONTINUITY_HANDOFF_NOTIFY_TOKEN=$HERMES_MISSION_CONTROL_API_KEY \
python3 scripts/capture_continuity_handoff.py --input handoff.json
```

The receiving API stores notifications at:

```text
lineage/continuity_handoff_notifications.jsonl
```

Use JSONL first. Turn on HTTP notification only after the desktop API address and token are confirmed.

## Desktop Smoke

Start the receiver on the desktop Hermes host:

```bash
cd /home/yk/physio-hermes-ops
git pull
HERMES_MISSION_CONTROL_HOST=0.0.0.0 \
HERMES_MISSION_CONTROL_PORT=8792 \
HERMES_MISSION_CONTROL_API_KEY=dev-local-mission-control \
python3 apps/api/mission_control_api.py
```

Then run this from MacBook:

```bash
python3 scripts/continuity_handoff_notify_smoke.py \
  --base-url http://100.83.147.56:8792 \
  --token dev-local-mission-control
```

Expected result:

```text
"ok": true
```

If `8791` returns `404 page not found`, another service is using that port. Use `8792` for Mission Control API.

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
