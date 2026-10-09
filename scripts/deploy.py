"""Pull the latest repo state and reconcile running services against it.

For each service directory under services/ whose files changed between the
previously-deployed commit and the fetched remote, runs `docker compose up -d`
to apply it. Shared env changes (services/shared/) redeploy every service.

Usage (run from the repo root):
  export SOPS_AGE_KEY_FILE=/path/to/age.key
  python -m scripts.deploy            # only touch services whose directory changed
  python -m scripts.deploy --force    # re-apply every service regardless of diff

Expects `git` and `docker` (with the compose plugin) on PATH. Takes an
flock-based lock on LOCK_FILE so an overlapping cron tick and webhook
trigger can't race each other.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import decrypt_secrets

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"
LOCK_FILE = Path(os.environ.get("DEPLOY_LOCK_FILE", "/tmp/homelab-deploy.lock"))
BRANCH = os.environ.get("BRANCH", "main")


class DeployError(RuntimeError):
    """Raised when a git or docker command fails."""


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{timestamp} {message}", flush=True)


def run(*args: str) -> str:
    try:
        result = subprocess.run(
            args, cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as exc:
        raise DeployError(f"{' '.join(args)} failed: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def changed_service_names(local: str, remote: str) -> set[str]:
    if local == remote:
        return set()
    diff = run("git", "diff", "--name-only", local, remote, "--", "services/")
    names = set()
    for line in diff.splitlines():
        parts = line.split("/")
        if len(parts) >= 2:
            names.add(parts[1])
    return names


def apply_service(service_dir: Path) -> None:
    log(f"applying {service_dir.name}")
    subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(service_dir),
            "pull",
            "--quiet",
        ],
        check=False,
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(service_dir),
            "up",
            "-d",
            "--remove-orphans",
            "--build",
            "--force-recreate",
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def prune_images() -> None:
    subprocess.run(["docker", "image", "prune", "-f"], check=False, capture_output=True)


def ensure_network(name: str) -> None:
    """Create the shared docker network `name` if it doesn't already exist.

    Services declare this network as `external: true`, so its lifecycle is
    independent of any single service's compose project — nothing should
    delete it just because e.g. traefik's stack gets torn down. Idempotent:
    safe to call on every deploy regardless of which services actually
    changed, or which order they get applied in.
    """
    exists = subprocess.run(
        ["docker", "network", "inspect", name], capture_output=True
    )
    if exists.returncode != 0:
        log(f"creating shared network {name}")
        subprocess.run(["docker", "network", "create", name], check=True)


def all_service_dirs() -> list[Path]:
    return sorted(
        p
        for p in SERVICES_DIR.iterdir()
        if p.is_dir() and p.name != "shared" and (p / "compose.yaml").is_file()
    )


def deploy(force: bool) -> int:
    run("git", "fetch", "--quiet", "origin", BRANCH)
    local = run("git", "rev-parse", "HEAD")
    remote = run("git", "rev-parse", f"origin/{BRANCH}")

    if local == remote and not force:
        log(f"up to date at {local}, nothing to do")
        return 0

    changed = changed_service_names(local, remote)
    shared_changed = "shared" in changed

    if local != remote:
        log(f"fast-forwarding {local} -> {remote}")
        run("git", "merge", "--ff-only", f"origin/{BRANCH}")

    rc = decrypt_secrets.main(["--all"])
    if rc != 0:
        log("decrypt failed, aborting")
        return rc

    ensure_network("proxy")

    failed = False
    for service_dir in all_service_dirs():
        if force or shared_changed or service_dir.name in changed:
            try:
                apply_service(service_dir)
            except subprocess.CalledProcessError as exc:
                print(
                    f"ERROR: {service_dir.name}: docker compose up failed "
                    f"(exit {exc.returncode})",
                    file=sys.stderr,
                )
                failed = True

    prune_images()
    if failed:
        log(f"deploy finished with errors at {remote}")
        return 1
    log(f"deploy complete at {remote}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="re-apply every service regardless of diff"
    )
    args = parser.parse_args(argv)

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock_fh:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("deploy already in progress, skipping")
            return 0

        try:
            return deploy(args.force)
        except DeployError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
