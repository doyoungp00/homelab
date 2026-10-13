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

import json
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

# Mirrors all_service_dirs()'s exclusion in scripts/deploy.py: `shared` isn't
# deployable, and `deploy-agent` can't safely redeploy itself mid-execution.
SERVICE_EXCLUDE = {"shared", "deploy-agent"}

deploy_lock = threading.Lock()

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Homelab Deploy</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }
  label { display: block; margin-top: 1rem; font-weight: 600; }
  input, select { width: 100%; padding: 0.4rem; margin-top: 0.25rem; box-sizing: border-box; }
  .checkbox-row { display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem; }
  .checkbox-row input { width: auto; }
  .checkbox-row label { margin: 0; font-weight: normal; }
  button { margin-top: 1.5rem; padding: 0.5rem 1.2rem; font-size: 1rem; cursor: pointer; }
  button:disabled { cursor: default; opacity: 0.6; }
  pre { background: #f0f0f0; padding: 0.75rem; margin-top: 1rem; white-space: pre-wrap; word-break: break-word; }
  .hint { color: #666; font-size: 0.85rem; margin-top: 1.5rem; }
</style>
</head>
<body>
<h1>Homelab Deploy</h1>

<label for="secret">Deploy secret</label>
<input id="secret" type="password" autocomplete="current-password">

<label for="service">Service</label>
<select id="service"><option value="">All services</option></select>

<div class="checkbox-row">
  <input id="force" type="checkbox" checked>
  <label for="force">Force recreate (always on when a specific service is picked)</label>
</div>

<button id="deploy-btn">Deploy</button>
<pre id="status"></pre>

<p class="hint">Watch the actual deploy output in Dozzle or <code>docker logs deploy-agent</code> — this page only shows whether the trigger was accepted.</p>

<script>
fetch("/services").then(r => r.json()).then(names => {
  const select = document.getElementById("service");
  for (const name of names) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }
});

const forceBox = document.getElementById("force");
document.getElementById("service").addEventListener("change", (e) => {
  forceBox.disabled = e.target.value !== "";
});

document.getElementById("deploy-btn").addEventListener("click", async () => {
  const btn = document.getElementById("deploy-btn");
  const status = document.getElementById("status");
  const secret = document.getElementById("secret").value;
  const service = document.getElementById("service").value;
  const force = forceBox.checked;

  const params = new URLSearchParams();
  if (service) {
    params.set("service", service);
  } else {
    params.set("force", force ? "true" : "false");
  }

  btn.disabled = true;
  status.textContent = "triggering...";
  try {
    const res = await fetch("/deploy?" + params.toString(), {
      method: "POST",
      headers: { "X-Deploy-Secret": secret },
    });
    const text = await res.text();
    status.textContent = res.status + " " + text;
  } catch (err) {
    status.textContent = "request failed: " + err;
  } finally {
    btn.disabled = false;
  }
});
</script>
</body>
</html>
"""


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


def deployable_service_names() -> list[str]:
    if not REPO_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in (REPO_DIR / "services").iterdir()
        if p.is_dir() and p.name not in SERVICE_EXCLUDE and (p / "compose.yaml").is_file()
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = PAGE_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/services":
            body = json.dumps(deployable_service_names()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

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
