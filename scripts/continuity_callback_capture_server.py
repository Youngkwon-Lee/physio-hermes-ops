#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture continuity callback payloads from desktop Hermes.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8891, help="Bind port.")
    parser.add_argument("--output", type=Path, required=True, help="JSON file to overwrite with the latest callback payload.")
    return parser.parse_args()


def make_handler(output_path: Path):
    class CallbackHandler(BaseHTTPRequestHandler):
        server_version = "ContinuityCallbackCapture/0.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            decoded = raw_body.decode("utf-8", errors="replace")
            try:
                payload = json.loads(decoded) if decoded.strip() else {}
            except json.JSONDecodeError:
                payload = {"rawBody": decoded}

            record = {
                "receivedAt": now_iso(),
                "method": "POST",
                "path": self.path,
                "headers": {key: value for key, value in self.headers.items()},
                "body": payload,
            }
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._json(
                200,
                {
                    "ok": True,
                    "storedAt": str(output_path),
                    "kind": payload.get("kind"),
                    "status": payload.get("status"),
                    "runId": payload.get("runId"),
                },
            )

        def do_GET(self) -> None:
            if self.path != "/health":
                return self._json(404, {"ok": False, "error": "not_found"})
            self._json(200, {"ok": True, "time": now_iso(), "output": str(output_path)})

    return CallbackHandler


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.output))
    print(
        json.dumps(
            {
                "ok": True,
                "host": args.host,
                "port": args.port,
                "output": str(args.output),
                "health": f"http://{args.host}:{args.port}/health",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
