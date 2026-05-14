#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
HOST = os.getenv("OPS_CTL_HOST", "127.0.0.1")
PORT = int(os.getenv("OPS_CTL_PORT", "8788"))
TOKEN = os.getenv("OPS_CTL_TOKEN", "")
READ_TOKEN = os.getenv("OPS_CTL_READ_TOKEN", TOKEN)
EXEC_TOKEN = os.getenv("OPS_CTL_EXEC_TOKEN", TOKEN)
EXEC_ADMIN_TOKEN = os.getenv("OPS_CTL_EXEC_ADMIN_TOKEN", EXEC_TOKEN)
EXEC_OPERATOR_TOKEN = os.getenv("OPS_CTL_EXEC_OPERATOR_TOKEN", "")
REQUIRE_TOKEN = os.getenv("OPS_CTL_REQUIRE_TOKEN", "1") == "1"
AUDIT_LOG = Path(os.getenv("OPS_CTL_AUDIT_LOG", str(ROOT / "lineage" / "actions_audit.jsonl")))
LOCK_PATH = Path(os.getenv("OPS_CTL_LOCK_FILE", str(ROOT / ".runtime" / "ops_control.lock")))
MAX_RETRIES = max(1, int(os.getenv("OPS_CTL_MAX_RETRIES", "2")))
RETRY_DELAY = float(os.getenv("OPS_CTL_RETRY_DELAY_SEC", "1.0"))

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

RUNTIME_LOCK = Lock()
ROLE_ACTIONS = {
    "admin": set(COMMANDS.keys()),
    "operator": {"refresh"},
}


def now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def audit(entry: dict):
    _ensure_parent(AUDIT_LOG)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_cmd(cmd, timeout_sec=180):
    attempts = []
    for n in range(1, MAX_RETRIES + 1):
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout_sec)
        rec = {
            "attempt": n,
            "exit_code": p.returncode,
            "stdout": (p.stdout or "")[-4000:],
            "stderr": (p.stderr or "")[-4000:],
        }
        attempts.append(rec)
        if p.returncode == 0:
            break
        if n < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    last = attempts[-1]
    return {
        "cmd": " ".join(cmd),
        "exit_code": last["exit_code"],
        "stdout": last["stdout"],
        "stderr": last["stderr"],
        "attempts": attempts,
    }


def read_recent_audits(limit=20):
    if not AUDIT_LOG.exists():
        return []
    rows = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    out = []
    for line in rows[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(out))


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

    def _require_auth(self, scope="read"):
        if not REQUIRE_TOKEN:
            return None

        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "", 1) if auth.startswith("Bearer ") else ""

        if scope == "read":
            expected = READ_TOKEN
            if not expected:
                self._json(500, {"ok": False, "error": "server_read_token_not_configured"})
                return None
            if token != expected:
                self._json(401, {"ok": False, "error": "unauthorized", "scope": scope})
                return None
            return {"scope": "read", "role": "viewer"}

        # exec scope: role is inferred by token
        admin = EXEC_ADMIN_TOKEN
        operator = EXEC_OPERATOR_TOKEN
        if not admin and not operator:
            self._json(500, {"ok": False, "error": "server_exec_token_not_configured"})
            return None

        if admin and token == admin:
            return {"scope": "exec", "role": "admin"}
        if operator and token == operator:
            return {"scope": "exec", "role": "operator"}

        self._json(401, {"ok": False, "error": "unauthorized", "scope": scope})
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {
                "ok": True,
                "time": now(),
                "auth_required": REQUIRE_TOKEN,
                "auth_mode": "split" if (READ_TOKEN != EXEC_TOKEN) else "single",
                "exec_roles": {
                    "admin_enabled": bool(EXEC_ADMIN_TOKEN),
                    "operator_enabled": bool(EXEC_OPERATOR_TOKEN),
                    "operator_actions": sorted(ROLE_ACTIONS.get("operator", set())),
                },
                "audit_log": str(AUDIT_LOG),
                "lock_file": str(LOCK_PATH),
            })
        if self.path.startswith("/actions/recent"):
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            return self._json(200, {"ok": True, "items": read_recent_audits(20)})
        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/action":
            return self._json(404, {"ok": False, "error": "not_found"})

        auth_ctx = self._require_auth("exec")
        if REQUIRE_TOKEN and not auth_ctx:
            return

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

        role = (auth_ctx or {}).get("role", "admin")
        allowed_actions = ROLE_ACTIONS.get(role, set())
        if action not in allowed_actions:
            return self._json(403, {
                "ok": False,
                "error": "forbidden_action",
                "role": role,
                "allowed_actions": sorted(allowed_actions),
            })

        if dry_run:
            payload = {
                "ok": True,
                "dry_run": True,
                "action": action,
                "role": role,
                "commands": [" ".join(c) for c in seq],
            }
            audit({"time": now(), "action": action, "role": role, "dry_run": True, "ok": True})
            return self._json(200, payload)

        with RUNTIME_LOCK:
            if LOCK_PATH.exists():
                return self._json(409, {"ok": False, "error": "busy", "lock_file": str(LOCK_PATH)})
            _ensure_parent(LOCK_PATH)
            LOCK_PATH.write_text(now(), encoding="utf-8")

            try:
                results = [run_cmd(c) for c in seq]
                ok = all(r["exit_code"] == 0 for r in results)
                payload = {
                    "ok": ok,
                    "action": action,
                    "role": role,
                    "time": now(),
                    "results": results,
                }
                audit({
                    "time": payload["time"],
                    "action": action,
                    "role": role,
                    "ok": ok,
                    "result_count": len(results),
                    "failed_commands": [r["cmd"] for r in results if r["exit_code"] != 0],
                })
                return self._json(200 if ok else 500, payload)
            finally:
                try:
                    LOCK_PATH.unlink(missing_ok=True)
                except Exception:
                    pass

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ops-control-api listening on http://{HOST}:{PORT} (auth_required={REQUIRE_TOKEN}, auth_mode={'split' if READ_TOKEN != EXEC_TOKEN else 'single'})")
    server.serve_forever()
