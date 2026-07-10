import json

import check_cron_registry as registry


def test_hermes_cron_command_uses_profile_when_present(monkeypatch):
    monkeypatch.setenv("HERMES_BIN", "hermes")

    command = registry.hermes_cron_command("macbookbridge")

    assert command == ["hermes", "-p", "macbookbridge", "cron", "list", "--all"]


def test_hermes_cron_command_uses_default_profile_when_missing(monkeypatch):
    monkeypatch.setenv("HERMES_BIN", "hermes")

    command = registry.hermes_cron_command(None)

    assert command == ["hermes", "cron", "list", "--all"]


def test_hermes_executable_falls_back_to_user_local_bin(tmp_path, monkeypatch):
    hermes = tmp_path / ".local" / "bin" / "hermes"
    hermes.parent.mkdir(parents=True)
    hermes.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.delenv("HERMES_BIN", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(registry.Path, "home", lambda: tmp_path)

    assert registry.hermes_executable() == str(hermes)


def test_registry_live_names_includes_runtime_name_and_aliases():
    names = registry.registry_live_names(
        {
            "name": "daily-ai-news-briefing",
            "runtime_name": "매일 05:30 AI 뉴스 브리프",
            "runtime_aliases": ["legacy-ai-news"],
        }
    )

    assert names == ["daily-ai-news-briefing", "매일 05:30 AI 뉴스 브리프", "legacy-ai-news"]


def test_runtime_only_job_names_are_sorted():
    names = registry.runtime_only_job_names(
        {
            "z-job": {"name": "z-job", "source_state": "runtime_only"},
            "tracked-job": {"name": "tracked-job"},
            "a-job": {"name": "a-job", "source_state": "runtime_only"},
        }
    )

    assert names == ["a-job", "z-job"]


def test_live_environment_issue_reports_empty_live_jobs():
    issue = registry.live_environment_issue(
        {"calendar-auto-classify": {"name": "calendar-auto-classify"}},
        {},
        "desktop",
    )

    assert issue is not None
    assert issue["kind"] == "no_live_jobs"
    assert issue["profile"] == "desktop"


def test_live_environment_issue_reports_wrong_profile_when_no_names_overlap():
    issue = registry.live_environment_issue(
        {"calendar-auto-classify": {"name": "calendar-auto-classify"}},
        {"agent-mesh-healthcheck": {"name": "agent-mesh-healthcheck"}},
        "macbookbridge",
    )

    assert issue is not None
    assert issue["kind"] == "no_registry_job_overlap"
    assert issue["profile"] == "macbookbridge"


def test_main_reports_live_command_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        registry,
        "load_registry",
        lambda: {
            "calendar-auto-classify": {
                "name": "calendar-auto-classify",
                "schedule": "10 23 * * *",
                "mode": "script",
                "script_file": "cron/scripts/calendar_auto_classify.py",
            }
        },
    )
    monkeypatch.setenv("HERMES_BIN", "/missing/hermes")
    monkeypatch.setattr(registry.sys, "argv", ["check_cron_registry.py", "--profile", "desktop"])

    exit_code = registry.main()
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert summary["environment_issue"]["kind"] == "live_command_failed"
    assert summary["environment_issue"]["profile"] == "desktop"
    assert "Hermes executable not found" in summary["environment_issue"]["message"]


def test_live_environment_issue_allows_runtime_name_overlap():
    issue = registry.live_environment_issue(
        {
            "daily-ai-news-briefing": {
                "name": "daily-ai-news-briefing",
                "runtime_name": "매일 05:30 AI 뉴스 브리프",
            }
        },
        {"매일 05:30 AI 뉴스 브리프": {"name": "매일 05:30 AI 뉴스 브리프"}},
        "default",
    )

    assert issue is None


def test_live_environment_issue_is_clear_when_any_job_overlaps():
    issue = registry.live_environment_issue(
        {"calendar-auto-classify": {"name": "calendar-auto-classify"}},
        {"calendar-auto-classify": {"name": "calendar-auto-classify"}},
        "desktop",
    )

    assert issue is None


def test_compare_matches_runtime_name_and_reports_real_schedule_mismatch():
    issues = registry.compare(
        {
            "daily-ai-news-briefing": {
                "name": "daily-ai-news-briefing",
                "runtime_name": "매일 05:30 AI 뉴스 브리프",
                "schedule": "30 5 * * *",
                "mode": "agent",
                "prompt_file": "cron/prompts/daily-ai-news-brief.md",
            }
        },
        {
            "매일 05:30 AI 뉴스 브리프": {
                "name": "매일 05:30 AI 뉴스 브리프",
                "schedule": "0 5 * * *",
                "mode": "agent",
            }
        },
    )

    assert {
        "severity": "error",
        "job": "daily-ai-news-briefing",
        "issue": "schedule_mismatch",
        "registry": "30 5 * * *",
        "live": "0 5 * * *",
    } in issues


def test_compare_allows_runtime_only_agent_without_prompt_file():
    issues = registry.compare(
        {
            "nightly-dev-sns-nudge": {
                "name": "nightly-dev-sns-nudge",
                "schedule": "50 23 * * *",
                "mode": "agent",
                "source_state": "runtime_only",
            }
        },
        {
            "nightly-dev-sns-nudge": {
                "name": "nightly-dev-sns-nudge",
                "schedule": "50 23 * * *",
                "mode": "agent",
            }
        },
    )

    assert issues == []


def test_main_reports_runtime_only_inventory(monkeypatch, capsys):
    monkeypatch.setattr(
        registry,
        "load_registry",
        lambda: {
            "runtime-agent": {
                "name": "runtime-agent",
                "schedule": "* * * * *",
                "mode": "agent",
                "source_state": "runtime_only",
            },
            "tracked-agent": {
                "name": "tracked-agent",
                "schedule": "0 5 * * *",
                "mode": "agent",
                "prompt_file": "cron/prompts/daily-ai-news-brief.md",
            },
        },
    )
    monkeypatch.setattr(
        registry,
        "get_live_jobs",
        lambda profile: {
            "runtime-agent": {"name": "runtime-agent", "schedule": "* * * * *", "mode": "agent"},
            "tracked-agent": {"name": "tracked-agent", "schedule": "0 5 * * *", "mode": "agent"},
        },
    )
    monkeypatch.setattr(registry.sys, "argv", ["check_cron_registry.py"])

    exit_code = registry.main()
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["runtime_only_jobs"] == 1
    assert summary["runtime_only_job_names"] == ["runtime-agent"]


def test_compare_allows_runtime_only_script_with_runtime_script():
    issues = registry.compare(
        {
            "desktop-secondbrain-codex-capture-4h": {
                "name": "desktop-secondbrain-codex-capture-4h",
                "schedule": "every 240m",
                "mode": "script",
                "source_state": "runtime_only",
                "runtime_script": "desktop-secondbrain-codex-capture-4h.sh",
            }
        },
        {
            "desktop-secondbrain-codex-capture-4h": {
                "name": "desktop-secondbrain-codex-capture-4h",
                "schedule": "every 240m",
                "mode": "script",
                "script": "desktop-secondbrain-codex-capture-4h.sh",
            }
        },
    )

    assert issues == []
