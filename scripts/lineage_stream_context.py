#!/usr/bin/env python3
import os
from typing import Dict, Optional


def build_stream_context(run_id: str = "") -> Dict[str, Optional[str]]:
    """Build channel/thread/stream metadata for lineage events.

    Priority:
    1) explicit env vars (best for real per-thread routing)
    2) run_id heuristic fallback
    """
    channel_id = (os.getenv("HERMES_CHANNEL_ID", "").strip() or None)
    thread_id = (os.getenv("HERMES_THREAD_ID", "").strip() or None)
    channel_name = (os.getenv("HERMES_CHANNEL_NAME", "").strip() or None)
    thread_name = (os.getenv("HERMES_THREAD_NAME", "").strip() or None)
    stream_id = (os.getenv("HERMES_STREAM_ID", "").strip() or None)

    run = (run_id or "").lower()
    if not stream_id:
        if thread_id:
            stream_id = f"thread:{thread_id}"
        elif channel_id:
            stream_id = f"channel:{channel_id}"
        elif "overnight" in run or "nightly" in run:
            stream_id = "overnight"
        elif "physio_bot" in run or "physio-bot" in run or run.startswith("dispatch-") or run.startswith("generation-close-"):
            stream_id = "physio_bot"
        elif "mem" in run:
            stream_id = "mem"
        else:
            stream_id = "unmapped"

    return {
        "stream_id": stream_id,
        "channel_id": channel_id,
        "thread_id": thread_id,
        "channel_name": channel_name,
        "thread_name": thread_name,
    }
