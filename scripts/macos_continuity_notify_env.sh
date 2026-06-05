#!/usr/bin/env bash
set -euo pipefail

# Set this to the real second-brain path on MacBook before sourcing if you want raw/candidate handoffs to avoid the local ops_knowledge fallback.
# Example:
# export SECOND_BRAIN_DIR="$HOME/projects/second-brain"

export CONTINUITY_HANDOFF_NOTIFY_URL="http://100.83.147.56:8792/handoff/notify"
export CONTINUITY_HANDOFF_NOTIFY_TOKEN="dev-local-mission-control"

echo "CONTINUITY_HANDOFF_NOTIFY_URL=$CONTINUITY_HANDOFF_NOTIFY_URL"
echo "CONTINUITY_HANDOFF_NOTIFY_TOKEN=$CONTINUITY_HANDOFF_NOTIFY_TOKEN"
echo "SECOND_BRAIN_DIR=${SECOND_BRAIN_DIR:-<unset>}"
