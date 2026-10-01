#!/usr/bin/env python3
"""Decrypt secret.sops.env files to individual .env files docker-compose needs.

For each target service directory:
  1. services/shared/env/secret.sops.env  (shared secrets, e.g. `APPDATA_ROOT`)
  2. <service>/secret.sops.env            (service-specific secrets)
  (in order, later key overrides colliding key)
and writes the merged plaintext to <service>/.env (mode 600, gitignored).

Usage:
  export SOPS_AGE_KEY_FILE=/path/to/age.key
  python scripts/decrypt_secrets.py --services <name> [<name> ...]
  python scripts/decrypt_secrets.py --all-services  # every service excluding shared
  python scripts/decrypt_secrets.py --shared
    # Decrypts `services/shared/env/secret.sops.env` to `services/shared/env/.env`
  python scripts/decrypt_secrets.py --all           # every service including shared
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sops_common import SopsError, decrypt_dotenv, is_encrypted_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"
SHARED_ENV_DIR = SERVICES_DIR / "shared" / "env"
SHARED_SECRET = SHARED_ENV_DIR / "secret.sops.env"


def parse_dotenv(text: str) -> dict[str, str]:
    """Splits dotenv text into an ordered dict."""

    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key] = value
    return values


def decrypt_for_service(service_dir: Path) -> Path | None:
    """Decrypt + merge secrets for one service directory.
    Returns the written .env path or `None` if there was nothing to decrypt."""

    merged: dict[str, str] = {}

    # dict.fromkeys dedupes while preserving order
    # if service_dir == SHARED_ENV_DIR: both entries are the same path so this decrypts it once.
    secret_files = dict.fromkeys((SHARED_SECRET, service_dir / "secret.sops.env"))
    for secret_file in secret_files:
        if not secret_file.is_file():
            continue
        if not is_encrypted_dotenv(secret_file):
            raise SopsError(f"{secret_file} is not a SOPS-encrypted dotenv file")
        merged.update(parse_dotenv(decrypt_dotenv(secret_file)))

    if not merged:
        return None

    env_path = service_dir / ".env"
    env_path.write_text("".join(f"{k}={v}\n" for k, v in merged.items()))
    os.chmod(env_path, 0o600)
    return env_path


def all_service_dirs() -> list[Path]:
    return sorted(
        p for p in SERVICES_DIR.iterdir() if p.is_dir() and p.name != "shared"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--services",
        nargs="+",
        metavar="NAME",
        help="service directory names under services/",
    )
    group.add_argument(
        "--shared",
        action="store_true",
        help="decrypt services/shared/env/secret.sops.env to services/shared/env/.env",
    )
    group.add_argument(
        "--all-services",
        action="store_true",
        help="decrypt for every service (not shared)",
    )
    group.add_argument(
        "--all", action="store_true", help="decrypt for every service, plus --shared"
    )
    args = parser.parse_args(argv)

    if args.shared:
        targets = [SHARED_ENV_DIR]
    elif args.all_services:
        targets = all_service_dirs()
    elif args.all:
        targets = [SHARED_ENV_DIR, *all_service_dirs()]
    else:
        targets = [SERVICES_DIR / name for name in args.services]

    failed = False
    for service_dir in targets:
        label = "shared" if service_dir == SHARED_ENV_DIR else service_dir.name
        if not service_dir.is_dir():
            print(f"ERROR: no such service directory: {service_dir}", file=sys.stderr)
            failed = True
            continue
        try:
            result = decrypt_for_service(service_dir)
        except SopsError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            failed = True
            continue
        if result is None:
            print(f"{label}: no secrets to decrypt")
        else:
            print(f"{label}: wrote {result}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
