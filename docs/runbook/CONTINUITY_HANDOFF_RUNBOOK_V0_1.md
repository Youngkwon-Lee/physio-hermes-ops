# CONTINUITY_HANDOFF_RUNBOOK_V0_1

## Purpose

Use this when MacBook Codex App, desktop Hermes, Discord, or Mission Control needs to hand work to another surface.

The goal is not to save every chat message.

The goal is to preserve enough state for another agent to continue safely.

## Canonical Run Rule

1. MacBook Codex creates a continuity handoff with the shared schema.
2. Raw and candidate artifacts write to `SECOND_BRAIN_DIR`, not repo-local fallback, unless explicitly testing fallback.
3. The same capture sends notify to desktop Hermes via `CONTINUITY_HANDOFF_NOTIFY_URL` when near-real-time delivery is wanted.
4. Desktop Hermes treats notify as an operational signal only; canonical promotion still requires later curation/approval.
5. Push continuity artifacts to GitHub at meaningful resume checkpoints, not on every tiny draft edit.

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

## WSL IP Change Recovery

When WSL restarts, the internal IP (for example `172.25.x.x`) may change and break the existing Windows `portproxy` target.

Use the repo script below from an **elevated Administrator PowerShell** on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\yk\physio-hermes-ops-wt-handoff\scripts\sync_mission_control_portproxy.ps1
```

What it does:
- reads the current WSL IPv4 via `wsl.exe hostname -I`
- resets `0.0.0.0:8792 -> <current-wsl-ip>:8792`
- keeps/creates firewall rule `MissionControl-8792`
- prints the final `netsh interface portproxy show all` table

Dry-run preview without admin write:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\yk\physio-hermes-ops-wt-handoff\scripts\sync_mission_control_portproxy.ps1 -DryRun
```

If needed, multiple ports can be synced together:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\yk\physio-hermes-ops-wt-handoff\scripts\sync_mission_control_portproxy.ps1 -Ports 8787,8791,8792
```

Recommended verify sequence after running the sync:

```powershell
netsh interface portproxy show all
```

Then from MacBook or another host:

```bash
python3 scripts/continuity_handoff_notify_smoke.py \
  --base-url http://100.83.147.56:8792 \
  --token dev-local-mission-control
```

## MacBook Default Notify Env

`capture_continuity_handoff.py` already reads these env vars by default:

```bash
export CONTINUITY_HANDOFF_NOTIFY_URL=http://100.83.147.56:8792/handoff/notify
export CONTINUITY_HANDOFF_NOTIFY_TOKEN=dev-local-mission-control
```

To keep raw/candidate handoffs out of the local `ops_knowledge/` fallback on MacBook, also set:

```bash
export SECOND_BRAIN_DIR=/absolute/path/to/your/second-brain
```

Repo helper snippet:

```bash
source scripts/macos_continuity_notify_env.sh
```

Recommended on MacBook for persistence:

```bash
printf '\n# Desktop Hermes continuity notify\nexport MISSION_CONTROL_BASE_URL="http://100.83.147.56:8792"\nexport MISSION_CONTROL_SHARED_TOKEN="dev-local-mission-control"\nexport CONTINUITY_HANDOFF_NOTIFY_URL="http://100.83.147.56:8792/handoff/notify"\nexport CONTINUITY_HANDOFF_NOTIFY_TOKEN="dev-local-mission-control"\nexport SECOND_BRAIN_DIR="/absolute/path/to/your/second-brain"\n' >> ~/.zshrc
source ~/.zshrc
```

For non-interactive zsh runs on MacBook, mirror the same exports into `~/.zshenv` if your Codex/script runner needs them there.

Quick verify on MacBook:

```bash
env | egrep 'MISSION_CONTROL|CONTINUITY_HANDOFF|SECOND_BRAIN_DIR'
```

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
