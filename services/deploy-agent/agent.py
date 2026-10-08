"""Entrypoint for the deploy-agent container.

Clones the homelab repo if it isn't already present, reconciles once on
startup, then for the life of the container:
  - a background thread re-runs `python -m scripts.deploy` every
    POLL_INTERVAL_SECONDS, picking up new commits on BRANCH
  - an HTTP server on PORT takes an immediate, LAN-only manual trigger:
      curl -X POST -H "X-Deploy-Secret: $WEBHOOK_SECRET" http://host:9000/deploy
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_DIR = Path(os.environ.get("REPO_DIR", "/repo"))
REPO_URL = os.environ["REPO_URL"]
BRANCH = os.environ.get("BRANCH", "main")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "900"))
PORT = int(os.environ.get("PORT", "9000"))
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

deploy_lock = threading.Lock()


def log(message: str) -> None:
    print(f"[agent] {message}", flush=True)


def ensure_clone() -> None:
    if (REPO_DIR / ".git").is_dir():
        return
    log(f"cloning {REPO_URL} into {REPO_DIR}")
    REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--branch", BRANCH, REPO_URL, str(REPO_DIR)], check=True
    )
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", str(REPO_DIR)],
        check=True,
    )


def run_deploy(force: bool) -> None:
    if not deploy_lock.acquire(blocking=False):
        log("deploy already running, skipping this trigger")
        return
    try:
        args = ["python3", "-m", "scripts.deploy"]
        if force:
            args.append("--force")
        subprocess.run(args, cwd=REPO_DIR)
    finally:
        deploy_lock.release()


def poll_loop() -> None:
    while True:
        time.sleep(POLL_INTERVAL_SECONDS)
        run_deploy(force=False)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/deploy":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("X-Deploy-Secret") != WEBHOOK_SECRET:
            self.send_response(401)
            self.end_headers()
            return
        threading.Thread(target=run_deploy, kwargs={"force": True}, daemon=True).start()
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"deploy triggered\n")

    def log_message(self, fmt: str, *args) -> None:
        log(fmt % args)


def main() -> int:
    ensure_clone()
    log("initial reconcile")
    run_deploy(force=True)

    threading.Thread(target=poll_loop, daemon=True).start()

    log(f"listening on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
