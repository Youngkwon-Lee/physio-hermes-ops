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


def test_matched_forbidden_pattern_flags_internal_paths():
    assert watchdog.matched_forbidden_pattern(
        "Record: /home/yk/physio-hermes-ops/dashboard/runtime/x.json",
        [r"/home/yk/"],
    ) == r"/home/yk/"


def test_matched_forbidden_pattern_allows_clean_human_text():
    assert watchdog.matched_forbidden_pattern(
        "재활 AI 브리프\n- 상태: 정상 실행\n- 신규 고신호: 0건",
        [r"/home/yk/", r"운영\s*메타"],
    ) is None


def test_matched_forbidden_pattern_flags_manifest_label():
    assert watchdog.matched_forbidden_pattern(
        "## Run Status\n- Manifest: 생성 완료, 상태 ok.",
        [r"Manifest\s*:", r"\bmanifest\b"],
    ) == r"Manifest\s*:"


def test_matched_forbidden_pattern_flags_tracking_log_tail():
    assert watchdog.matched_forbidden_pattern(
        "추적/실행 기록\n- raw 후보를 /tmp에 JSON으로 저장하고 guard를 실행했습니다.",
        [r"추적[/\s]*실행\s*기록", r"raw\s*후보를\s*/tmp"],
    ) == r"추적[/\s]*실행\s*기록"
