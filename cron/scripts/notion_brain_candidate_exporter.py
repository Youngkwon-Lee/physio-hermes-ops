#!/usr/bin/env python3
from __future__ import annotations

import json

def main() -> int:
    print(json.dumps({"ok": False, "source_state": "public_safe_template", "job": "notion-brain-candidate-exporter-daily"}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
