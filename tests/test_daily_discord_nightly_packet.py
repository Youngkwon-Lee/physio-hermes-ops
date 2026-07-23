import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "cron" / "scripts" / "daily_discord_nightly_packet.py"
spec = importlib.util.spec_from_file_location("daily_discord_nightly_packet", SCRIPT_PATH)
packet = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(packet)


def test_compact_detail_masks_paths_and_ids():
    text = (
        "Output saved to: /home/yk/.hermes/cron/output/851/file.md "
        "source: /home/yk/.hermes/cron/output/851/file.md "
        "candidate: /home/yk/brain-linux/candidates/discord.md "
        "commit: a9ff1144f071c25b0724446b7d6c2f65d8dd1452 "
        "notion_db_id: abc longterm_memory_db_id: def"
    )

    compact = packet.compact_detail(text)

    assert "/home/yk/" not in compact
    assert "a9ff1144f071c25b0724446b7d6c2f65d8dd1452" not in compact
    assert "output saved" in compact
