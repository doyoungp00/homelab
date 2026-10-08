"""Push edits made to a local .env back into its encrypted secret.sops.env.

  - Key already exists in the service's own secret.sops.env:
    -> New value is pushed.
  - Key only exists in the shared secret, value unchanged:
    -> Left alone (it's still coming from shared).
  - Key only exists in the shared secret, value changed:
    -> Written as a new key in the service's own secret.sops.env (becomes local override)
       (A warning is shown that the new key shadows the shared key.)
  - Key does not exist anywhere:
    -> Written as a new key.

Keys that exist in the service's own secret.sops.env but are missing
from .env are left untouched and reported as a warning, never deleted
automatically.

To add or edit an actually-shared key, use --shared.
It decrypts and re-encrypts services/shared/env/secret.sops.env
directly with none of the per-service shadowing logic above.

Usage (run from the repo root):
  export SOPS_AGE_KEY_FILE=/path/to/age.key
  python -m scripts.decrypt_secrets --services <name>   # edit the .env it writes
  python -m scripts.encrypt_secrets --services <name> [<name> ...]
  python -m scripts.encrypt_secrets --all-services      # every service, not shared

  python -m scripts.decrypt_secrets --shared            # edit services/shared/env/.env
  python -m scripts.encrypt_secrets --shared            # write back

  python -m scripts.encrypt_secrets --all               # every service including shared

In order to drop an old key from secret.sops.env:
  sops unset --input-type dotenv --output-type dotenv path/to/secret.sops.env '["KEY_NAME"]'
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .sops_common import (
    SopsError,
    decrypt_dotenv,
    is_encrypted_dotenv,
    run_sops,
    set_dotenv_value,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"
SHARED_ENV_DIR = SERVICES_DIR / "shared" / "env"
SHARED_SECRET = SHARED_ENV_DIR / "secret.sops.env"


def parse_dotenv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key] = value
    return values


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_dotenv(path.read_text())


def decrypted(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    if not is_encrypted_dotenv(path):
        raise SopsError(f"{path} is not a SOPS-encrypted dotenv file")
    return parse_dotenv(decrypt_dotenv(path))


def bootstrap_encrypt(path: Path, values: dict[str, str]) -> None:
    """Create a brand-new secret.sops.env from scratch and encrypt it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    run_sops("-e", "-i", str(path))


def apply_updates(secret_path: Path, updates: dict[str, str]) -> None:
    if secret_path.is_file():
        for key, value in updates.items():
            set_dotenv_value(secret_path, key, value)
    else:
        bootstrap_encrypt(secret_path, updates)


def push_shared() -> None:
    env_path = SHARED_ENV_DIR / ".env"
    if not env_path.is_file():
        print("shared: no .env found, nothing to push")
        return

    current = load_dotenv(env_path)
    original = decrypted(SHARED_SECRET)

    updates = {k: v for k, v in current.items() if original.get(k) != v}
    orphaned = set(original) - set(current)

    if updates:
        apply_updates(SHARED_SECRET, updates)
        print(
            f"shared: pushed {len(updates)} key(s) "
            f"to {SHARED_SECRET.relative_to(REPO_ROOT)}: {', '.join(sorted(updates))}"
        )
    else:
        print("shared: no changes to push")

    if orphaned:
        print(
            f"shared: WARNING: {', '.join(sorted(orphaned))} exist in "
            f"{SHARED_SECRET.relative_to(REPO_ROOT)} but are missing from .env — "
            f"left untouched, not deleted. Remove manually with 'sops' if intentional.",
            file=sys.stderr,
        )


def push_for_service(service_dir: Path) -> None:
    env_path = service_dir / ".env"
    if not env_path.is_file():
        print(f"{service_dir.name}: no .env found, nothing to push")
        return

    current = load_dotenv(env_path)
    service_secret = service_dir / "secret.sops.env"
    original_service = decrypted(service_secret)
    original_shared = decrypted(SHARED_SECRET)

    updates: dict[str, str] = {}
    shadow_warnings: list[str] = []

    for key, value in current.items():
        if key in original_service:
            if original_service[key] != value:
                updates[key] = value
        elif key in original_shared:
            if original_shared[key] != value:
                updates[key] = value
                shadow_warnings.append(key)
            # else: value matches shared, still sourced from shared, no-op
        else:
            updates[key] = value

    orphaned = set(original_service) - set(current)

    if updates:
        apply_updates(service_secret, updates)
        print(
            f"{service_dir.name}: pushed {len(updates)} key(s) "
            f"to {service_secret.relative_to(REPO_ROOT)}: {', '.join(sorted(updates))}"
        )
    else:
        print(f"{service_dir.name}: no changes to push")

    if shadow_warnings:
        plural = len(shadow_warnings) != 1
        print(
            f"{service_dir.name}: WARNING: {', '.join(sorted(shadow_warnings))} "
            f"diverged from the shared value and {'were' if plural else 'was'} written as "
            f"local override(s) in {service_secret.relative_to(REPO_ROOT)} — the shared "
            f"default no longer applies here. If unintentional, revert the value in .env "
            f"and re-run. To change the shared value itself, use --shared instead.",
            file=sys.stderr,
        )

    if orphaned:
        print(
            f"{service_dir.name}: WARNING: {', '.join(sorted(orphaned))} exist in "
            f"{service_secret.relative_to(REPO_ROOT)} but are missing from .env — "
            f"left untouched, not deleted. Remove manually with 'sops' if intentional.",
            file=sys.stderr,
        )


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
        help="push services/shared/env/.env back to services/shared/env/secret.sops.env",
    )
    group.add_argument(
        "--all-services",
        action="store_true",
        help="push for every service (not shared)",
    )
    group.add_argument(
        "--all", action="store_true", help="push for every service, plus --shared"
    )
    args = parser.parse_args(argv)

    push_shared_first = args.shared or args.all
    service_targets: list[Path] = []
    if args.all_services or args.all:
        service_targets = all_service_dirs()
    elif args.services:
        service_targets = [SERVICES_DIR / name for name in args.services]

    failed = False

    if push_shared_first:
        try:
            push_shared()
        except SopsError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            failed = True

    for service_dir in service_targets:
        if not service_dir.is_dir():
            print(f"ERROR: no such service directory: {service_dir}", file=sys.stderr)
            failed = True
            continue
        try:
            push_for_service(service_dir)
        except SopsError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
