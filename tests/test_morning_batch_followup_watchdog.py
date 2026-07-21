import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = ROOT / "cron" / "scripts" / "morning_batch_followup_watchdog.py"
spec = importlib.util.spec_from_file_location("morning_batch_followup_watchdog", WATCHDOG_PATH)
watchdog = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(watchdog)


def test_has_mixed_silent_token_allows_exact_silent():
    assert watchdog.has_mixed_silent_token("[SILENT]") is False


def test_has_mixed_silent_token_flags_content_plus_silent():
    assert watchdog.has_mixed_silent_token("보고 내용\n\n[SILENT]") is True
