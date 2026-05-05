from __future__ import annotations

import json
import random
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _safe_path_part(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")
    return cleaned or "unknown"


def _json_id(path: Path, key: str) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get(key)
    except (OSError, json.JSONDecodeError):
        value = None
    return _safe_path_part(value or path.stem)


def _new_output_dir(save_dir: Path, family_id: str, bundle_id: str) -> tuple[str, Path]:
    for _ in range(100):
        random_id = f"{random.randint(0, 9999):04d}"
        feedback_id = f"{family_id}_{bundle_id}_{random_id}"
        output_dir = save_dir / feedback_id
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
            return feedback_id, output_dir

    raise FileExistsError("Could not create a unique feedback directory")


def start_feedback_server(save_dir: Path) -> str:
    save_dir.mkdir(parents=True, exist_ok=True)

    class FeedbackHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send_json(200, {"ok": True})

        def do_POST(self) -> None:
            if self.path != "/save_feedback":
                self._send_json(404, {"ok": False, "error": "Unknown endpoint"})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(400, {"ok": False, "error": "Invalid JSON payload"})
                return

            if not isinstance(payload, dict):
                self._send_json(400, {"ok": False, "error": "Payload must be a JSON object"})
                return

            source_files = payload.pop("source_files", {})
            family_app_path = Path(source_files.get("family_application", ""))
            document_bundle_path = Path(source_files.get("document_bundle", ""))
            if not family_app_path.is_file() or not document_bundle_path.is_file():
                self._send_json(400, {"ok": False, "error": "Source files were not found"})
                return

            family_id = _json_id(family_app_path, "family_id")
            bundle_id = _json_id(document_bundle_path, "bundle_id")
            try:
                feedback_id, output_dir = _new_output_dir(save_dir, family_id, bundle_id)
            except FileExistsError:
                self._send_json(500, {"ok": False, "error": "Could not create save directory"})
                return

            family_output_path = output_dir / f"family_application{family_app_path.suffix}"
            bundle_output_path = output_dir / f"document_bundle{document_bundle_path.suffix}"
            output_path = output_dir / "feedback.json"

            shutil.copy2(family_app_path, family_output_path)
            shutil.copy2(document_bundle_path, bundle_output_path)
            output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"Feedback saved to: {output_dir}", flush=True)

            self._send_json(
                200,
                {
                    "ok": True,
                    "id": feedback_id,
                    "directory": str(output_dir),
                    "files": [
                        str(family_output_path),
                        str(bundle_output_path),
                        str(output_path),
                    ],
                },
            )

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), FeedbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return f"http://{host}:{port}/save_feedback"
