"""Entrypoint for the deploy-agent container.

Clones the homelab repo if it isn't already present, reconciles once on
startup, then for the life of the container:
  - a background thread re-runs `python -m scripts.deploy` every
    POLL_INTERVAL_SECONDS, picking up new commits on BRANCH
  - an HTTP server on PORT takes an immediate, LAN-only manual trigger:
      curl -X POST -H "X-Deploy-Secret: $WEBHOOK_SECRET" http://host:9000/deploy
    Defaults to force-recreating every service. Add ?force=false to instead
    only apply services whose directory actually changed, same as a poll tick:
      curl -X POST -H "X-Deploy-Secret: $WEBHOOK_SECRET" "http://host:9000/deploy?force=false"
    Add ?service=<name> to only redeploy that one service (always forced —
    no reason to single one out and not force it; force is ignored if given):
      curl -X POST -H "X-Deploy-Secret: $WEBHOOK_SECRET" "http://host:9000/deploy?service=nextcloud-aio"
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
    if not (REPO_DIR / ".git").is_dir():
        log(f"cloning {REPO_URL} into {REPO_DIR}")
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--branch", BRANCH, REPO_URL, str(REPO_DIR)], check=True
        )
    # Also needed when /repo was pre-cloned on the host (per first-setup.md)
    # rather than by this function — git flags ownership as "dubious" whenever
    # the container's UID doesn't match the files', regardless of who cloned it.
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", str(REPO_DIR)],
        check=True,
    )


def run_deploy(force: bool, service: str | None = None) -> None:
    if not deploy_lock.acquire(blocking=False):
        log("deploy already running, skipping this trigger")
        return
    try:
        args = ["python3", "-m", "scripts.deploy"]
        if service:
            args.extend(["--service", service])
        elif force:
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
        parsed = urlparse(self.path)
        if parsed.path != "/deploy":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("X-Deploy-Secret") != WEBHOOK_SECRET:
            self.send_response(401)
            self.end_headers()
            return
        # Defaults to force (recreate everything) to match how this endpoint
        # has always behaved; ?force=false opts into the targeted, diff-only
        # behavior the poll loop uses instead. ?service=<name> overrides both,
        # always forced — there's no scenario where you'd single out a
        # service and not want it applied.
        query = parse_qs(parsed.query)
        service = query.get("service", [None])[0]
        raw_force = query.get("force", ["true"])[0]
        force = raw_force.lower() not in ("false", "0", "no")
        threading.Thread(
            target=run_deploy, kwargs={"force": force, "service": service}, daemon=True
        ).start()
        self.send_response(202)
        self.end_headers()
        self.wfile.write(
            f"deploy triggered (service={service or 'all'}, force={force})\n".encode()
        )

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
