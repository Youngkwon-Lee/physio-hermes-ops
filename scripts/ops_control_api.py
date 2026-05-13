#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = os.getenv("OPS_CTL_HOST", "127.0.0.1")
PORT = int(os.getenv("OPS_CTL_PORT", "8788"))
TOKEN = os.getenv("OPS_CTL_TOKEN", "")

COMMANDS = {
    "refresh": [["python3", "scripts/export_cron_status.py"]],
    "pause_all": [
        ["hermes", "cron", "pause", "61fbb6fbc580"],
        ["hermes", "cron", "pause", "3320eb412834"],
        ["hermes", "cron", "pause", "8d13ba66655d"],
        ["hermes", "cron", "pause", "b96d745a16c9"],
        ["hermes", "cron", "pause", "9f39d5d4dd0a"],
        ["hermes", "cron", "pause", "22e0930cff69"],
        ["hermes", "cron", "pause", "4fa36ebb15d2"],
        ["python3", "scripts/export_cron_status.py"],
    ],
    "resume_core": [
        ["hermes", "cron", "resume", "61fbb6fbc580"],
        ["hermes", "cron", "resume", "3320eb412834"],
        ["hermes", "cron", "resume", "8d13ba66655d"],
        ["hermes", "cron", "resume", "b96d745a16c9"],
        ["hermes", "cron", "resume", "9f39d5d4dd0a"],
        ["python3", "scripts/export_cron_status.py"],
    ],
    "finalize_once": [
        ["hermes", "cron", "run", "4fa36ebb15d2"],
        ["hermes", "cron", "pause", "4fa36ebb15d2"],
        ["python3", "scripts/export_cron_status.py"],
    ],
}


def run_cmd(cmd):
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": " ".join(cmd),
        "exit_code": p.returncode,
        "stdout": (p.stdout or "")[-4000:],
        "stderr": (p.stderr or "")[-4000:],
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True, "time": datetime.now().isoformat(timespec="seconds")})
        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/action":
            return self._json(404, {"ok": False, "error": "not_found"})

        if TOKEN:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {TOKEN}":
                return self._json(401, {"ok": False, "error": "unauthorized"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"ok": False, "error": "invalid_json"})

        action = str(data.get("action", "")).strip()
        dry_run = bool(data.get("dry_run", False))
        seq = COMMANDS.get(action)
        if not seq:
            return self._json(400, {"ok": False, "error": "unknown_action", "allowed": sorted(COMMANDS)})

        if dry_run:
            return self._json(200, {
                "ok": True,
                "dry_run": True,
                "action": action,
                "commands": [" ".join(c) for c in seq],
            })

        results = [run_cmd(c) for c in seq]
        ok = all(r["exit_code"] == 0 for r in results)
        return self._json(200 if ok else 500, {
            "ok": ok,
            "action": action,
            "time": datetime.now().isoformat(timespec="seconds"),
            "results": results,
        })

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ops-control-api listening on http://{HOST}:{PORT}")
    server.serve_forever()
