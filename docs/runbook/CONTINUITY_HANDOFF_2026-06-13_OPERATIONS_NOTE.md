# CONTINUITY_HANDOFF_2026-06-13_OPERATIONS_NOTE

## Summary

MacBook continuity handoff smoke is healthy again when routed through `http://100.83.147.56:8792`.

## Final Status

- `GET /health` -> `200`
- `POST /handoff/notify` -> `200`
- `python3 scripts/continuity_handoff_notify_smoke.py ...` -> `"ok": true`
- delayed callback to MacBook `/ack` -> received

## What Failed

- MacBook to WSL direct path `http://100.125.26.99:8792` timed out.
- Windows host path `http://100.83.147.56:8792` answered health checks but initially returned `401` for notify.

## Root Cause

The MacBook continuity scripts sent only `x-hermes-api-key`.

The active notify receiver path accepted `Authorization: Bearer <shared-token>`.

## Fix Applied

- `scripts/continuity_handoff_notify_smoke.py` now sends both:
  - `Authorization: Bearer <token>`
  - `x-hermes-api-key: <token>`
- `scripts/capture_continuity_handoff.py` now sends both headers too.
- `scripts/continuity_handoff_notify_smoke.py` now supports:
  - `--callback-url`
  - `--surface`
  - `--run-id`
  - `--goal`
  - `--verbose`
- `scripts/continuity_callback_capture_server.py` was added for MacBook callback capture.
- Both scripts now accept `MISSION_CONTROL_BASE_URL` and `MISSION_CONTROL_SHARED_TOKEN` as primary MacBook env defaults.

## Callback Verification

Full delayed callback verification also passed later on June 13, 2026.

- MacBook callback receiver listened on `0.0.0.0:8891`
- desktop direct Tailscale path `http://100.125.26.99:8792` accepted the handoff
- desktop later called back to `http://100.83.163.42:8891/ack`
- MacBook captured:
  - `kind: "continuity_handoff_ack"`
  - `status: "ack"`
  - `runId: "cross-device-callback-smoke-2"`

## Safe Operational Default

Use this on MacBook until direct WSL routing is proven stable:

```bash
export MISSION_CONTROL_BASE_URL="http://100.83.147.56:8792"
export MISSION_CONTROL_SHARED_TOKEN="<shared-token>"
export CONTINUITY_HANDOFF_NOTIFY_URL="http://100.83.147.56:8792/handoff/notify"
export CONTINUITY_HANDOFF_NOTIFY_TOKEN="$MISSION_CONTROL_SHARED_TOKEN"
```

## Follow-Up

- Keep Windows host path as canonical external smoke route for now.
- Use the direct WSL path separately when you need to validate delayed callback delivery.
