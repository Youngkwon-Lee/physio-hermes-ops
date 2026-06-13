#!/usr/bin/env bash
set -euo pipefail

# Set this to the real second-brain path on MacBook before sourcing if you want raw/candidate handoffs to avoid the local ops_knowledge fallback.
# Example:
# export SECOND_BRAIN_DIR="$HOME/projects/second-brain"

# Default to the desktop WSL/Linux Tailscale IP for direct receiver access.
# If you intentionally route through the Windows host portproxy instead,
# override this before sourcing or export a different value afterwards.
export CONTINUITY_HANDOFF_NOTIFY_URL="http://100.125.26.99:8792/handoff/notify"
export CONTINUITY_HANDOFF_NOTIFY_TOKEN="dev-local-mission-control"

echo "CONTINUITY_HANDOFF_NOTIFY_URL=$CONTINUITY_HANDOFF_NOTIFY_URL"
echo "CONTINUITY_HANDOFF_NOTIFY_TOKEN=$CONTINUITY_HANDOFF_NOTIFY_TOKEN"
echo "SECOND_BRAIN_DIR=${SECOND_BRAIN_DIR:-<unset>}"
