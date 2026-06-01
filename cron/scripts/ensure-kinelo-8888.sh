#!/usr/bin/env bash
# Public-safe template of the runtime Kinelo watchdog script.
# Runtime truth lives in ~/.hermes/scripts/ensure-kinelo-8888.sh.
set -euo pipefail

ROOT="${KINELO_ROOT_DIR}"
PORT="8888"
LOG="${KINELO_HTTP_LOG}"

if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  exit 0
fi

mkdir -p "$ROOT"
nohup python3 -m http.server "$PORT" --directory "$ROOT" >>"$LOG" 2>&1 </dev/null &
sleep 1
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  echo "Started Kinelo review_apps server on http://127.0.0.1:${PORT}"
else
  echo "Failed to start Kinelo review_apps server on port ${PORT}" >&2
  exit 1
fi
