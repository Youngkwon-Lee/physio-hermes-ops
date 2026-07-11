#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOW_PATH_PATTERNS = [
    re.compile(r"^docs/"),
    re.compile(r"^tests/"),
    re.compile(r"^deploy/systemd/.*\.env\.example$"),
    re.compile(r"^dashboard/config\.example\.js$"),
]
TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".example",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".service",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
SECRET_RULES = {
    "generic_secret_assignment": re.compile(
        r"""(?i)(api[_-]?key|secret|token|password|client[_-]?secret|private[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"\s]{12,}['"]"""
    ),
    "hometax_codef_credential": re.compile(
        r"""(?i)(codef|hometax).{0,40}(client[_-]?secret|password|cert|private[_-]?key|account|token)\s*[:=]\s*['"][^'"\s]{8,}['"]"""
    ),
    "database_url_assignment": re.compile(
        r"""(?i)(database_url|postgres_url|postgresql_url)\s*[:=]\s*['"]postgres(?:ql)?://[^'"]+['"]"""
    ),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    rule: str
    count: int


def tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in proc.stdout.splitlines() if line.strip()]


def is_allowed(rel_path: str) -> bool:
    return any(pattern.search(rel_path) for pattern in ALLOW_PATH_PATTERNS)


def is_text_candidate(path: Path) -> bool:
    if path.name in {".gitleaks.toml", ".gitignore", "Makefile", "README.md", "AGENTS.md", "CLAUDE.md"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def scan_file(path: Path) -> list[Finding]:
    rel_path = path.relative_to(ROOT).as_posix()
    if is_allowed(rel_path) or not is_text_candidate(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for rule, pattern in SECRET_RULES.items():
        count = len(pattern.findall(text))
        if count:
            findings.append(Finding(path=rel_path, rule=rule, count=count))
    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in tracked_files():
        findings.extend(scan_file(path))

    report = {
        "scanner": "secret_scan_readiness.v1",
        "redacted": True,
        "finding_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
