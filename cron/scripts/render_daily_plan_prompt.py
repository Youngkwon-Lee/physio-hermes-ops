#!/usr/bin/env python3
"""Render the deterministic Discord morning-plan prompt."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


def render_prompt(anchor: dt.date) -> str:
    return "\n".join(
        [
            f"# 오늘 할 일 · {anchor.isoformat()}",
            "오늘 실제로 끝내고 싶은 일 1~3개만 적어주세요.",
            "",
            "아래 형식 그대로 답하면 계획 후보로 자동 기록됩니다.",
            "```",
            "오늘 할 일",
            "1. 가장 중요한 일",
            "2. 두 번째 일",
            "3. 세 번째 일",
            "```",
            "계획을 세우지 않는 날은 `오늘 계획 패스`라고 답하면 됩니다.",
            "[daily-plan-prompt-v1]",
        ]
    )


def main() -> int:
    print(render_prompt(dt.datetime.now(KST).date()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
