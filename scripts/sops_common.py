"""Shared SOPS execution helpers.

Subprocess wrapper around the `sops` CLI plus a structural check
for whether a dotenv file is SOPS-encrypted.
No custom crypto here. `sops` does all the actual encryption/decryption.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

_MAC_RE = re.compile(r"^sops_mac=ENC\[AES256_GCM,")
_VERSION_RE = re.compile(r"^sops_version=")
_ENCRYPTED_VALUE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=ENC\[AES256_GCM,")


class SopsError(RuntimeError):
    """Raised when a `sops` invocation fails."""


def run_sops(
    *args: str, check: bool = True, input: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the `sops` CLI with the given arguments.

    Relies on `sops` being on PATH.
    `SOPS_AGE_KEY_FILE` / `SOPS_AGE_KEY` / `SOPS_AGE_KEY_CMD` are read from the environment by sops itself.
    """

    try:
        return subprocess.run(
            ["sops", *args],
            check=check,
            capture_output=True,
            text=True,
            input=input,
        )
    except FileNotFoundError as exc:
        raise SopsError("sops is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise SopsError(f"sops {' '.join(args)} failed: {exc.stderr.strip()}") from exc


def is_encrypted_dotenv(path: Path) -> bool:
    """Structural check only, no decryption attempted."""

    if not path.is_file():
        return False

    has_mac = has_version = has_value = False
    for line in path.read_text().splitlines():
        if _MAC_RE.match(line):
            has_mac = True
        elif _VERSION_RE.match(line):
            has_version = True
        elif _ENCRYPTED_VALUE_RE.match(line):
            has_value = True

    return has_mac and has_version and has_value


def decrypt_dotenv(path: Path) -> str:
    """Decrypt a SOPS-encrypted dotenv file and return its plaintext contents."""

    result = run_sops("-d", str(path))
    return result.stdout


def set_dotenv_value(path: Path, key: str, value: str) -> None:
    """Set a single key's value in an existing SOPS-encrypted dotenv file,
    leaving every other key and the file's structure untouched."""

    run_sops(
        "set",
        "--input-type",
        "dotenv",
        "--output-type",
        "dotenv",
        "--value-stdin",
        str(path),
        json.dumps([key]),
        input=json.dumps(value) + "\n",
    )
