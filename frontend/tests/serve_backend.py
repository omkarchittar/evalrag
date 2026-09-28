"""Disposable PostgreSQL/API/worker fixture. Never uses a real model or production data."""

import json
import os
import signal
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psycopg
from evalrag.models import User
from evalrag.security import hash_password
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PASSWORD = "browser-fixture-password-2026"
stop = threading.Event()
for sig in [signal.SIGTERM, signal.SIGINT]:
    signal.signal(sig, lambda *_: stop.set())


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):
            payload = {
                "model": body["model"],
                "data": [
                    {"index": i, "embedding": [1.0] + [0.0] * (body["dimensions"] - 1)}
                    for i, _ in enumerate(body["input"])
                ],
                "usage": {"prompt_tokens": 24},
            }
        else:
            context = json.loads(body["messages"][1]["content"])
            if "provider failure" in context["question"].lower():
                self.send_response(503)
                self.end_headers()
                return
            if "claim_support" in body["response_format"]["json_schema"]["schema"]["properties"]:
                value = {
                    "claim_support": [True] * len(context["claims"]),
                    "citation_support": [True] * len(context["citations"]),
                    "answer_relevance": 1.0,
                    "explanation": "Controlled browser fixture; not a quality measurement.",
                }
            elif "moon" in context["question"].lower():
                value = {
                    "abstained": True,
                    "reason": "No evidence for a moon policy in these sources.",
                    "claims": [],
                }
            else:
                source = context["sources"][0]
                quote = "The daily meal allowance is 75 dollars."
                value = {
                    "abstained": False,
                    "reason": None,
                    "claims": [
                        {
                            "text": quote,
                            "citations": [{"chunk_id": source["chunk_id"], "quote": quote}],
                        }
                    ],
                }
            if (
                body.get("tools")
                and "calculate" in context["question"].lower()
                and len(body["messages"]) == 2
            ):
                message = {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "browser-calculator",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": '{"expression":"75*3"}',
                            },
                        }
                    ],
                }
                finish = "tool_calls"
            else:
                message = {"content": json.dumps(value)}
                finish = "stop"
            payload = {
                "model": "controlled-browser-fixture",
                "choices": [{"finish_reason": finish, "message": message}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 50},
            }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    if not os.environ.get("TEST_DATABASE_URL"):
        raise SystemExit(
            "TEST_DATABASE_URL must name an isolated PostgreSQL test database; its user needs CREATEDB."
        )
    original = make_url(os.environ["TEST_DATABASE_URL"])
    name = "evalrag_browser_" + uuid.uuid4().hex[:10]
    target = original.set(database=name)
    admin_url = original.set(drivername="postgresql").render_as_string(hide_password=False)
    target_url = target.render_as_string(hide_password=False)
    provider = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    env = {
        **os.environ,
        "TEST_DATABASE_URL": target_url,
        "EVALRAG_DATABASE_URL": target_url,
        "EVALRAG_OPENAI_API_KEY": "controlled-fixture-key",
        "EVALRAG_OPENAI_BASE_URL": f"http://127.0.0.1:{provider.server_port}/v1",
        "EVALRAG_GENERATION_MODEL": "controlled-browser-fixture",
        "EVALRAG_UPLOAD_LIMIT_BYTES": "32000000",
        "EVALRAG_ALLOWED_ORIGINS": '["http://127.0.0.1:3110"]',
    }
    processes = []
    python = str(BACKEND / ".venv/bin/python")
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            subprocess.run(
                [str(BACKEND / ".venv/bin/alembic"), "upgrade", "head"],
                cwd=BACKEND,
                env=env,
                check=True,
                capture_output=True,
            )
            engine = create_engine(target_url)
            with Session(engine) as db, db.begin():
                for email, display, role in [
                    ("viewer@example.com", "Jordan Lee", "member"),
                    ("admin@example.com", "Casey Rivera", "admin"),
                    ("other@example.com", "Alex Chen", "member"),
                ]:
                    db.add(
                        User(
                            email=email,
                            name=display,
                            role=role,
                            password_hash=hash_password(PASSWORD),
                        )
                    )
            engine.dispose()
            for command in [
                [
                    python,
                    "-m",
                    "uvicorn",
                    "evalrag.app:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "18080",
                    "--no-access-log",
                ],
                [python, "-m", "evalrag.worker"],
            ]:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=BACKEND,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            print(
                "Disposable browser backend started with a controlled provider.",
                flush=True,
            )
            while not stop.wait(0.5):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("Browser fixture process exited")
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            provider.shutdown()
            provider.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
