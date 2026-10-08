"""Pure helper functions for the scripts/ test suite. No pytest fixtures used.
Only building blocks the fixtures in conftest.py (and a few tests directly) compose.
Keeps everything confined to a temp directory with a disposable age key.
Tests must never read or write the real repo's services/, age.key, or .sops.yaml.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

SOPS_AVAILABLE = shutil.which("sops") is not None
AGE_KEYGEN_AVAILABLE = shutil.which("age-keygen") is not None


def generate_age_key(path: Path) -> str:
    """Generate a disposable age keypair at `path` and return its public key."""
    subprocess.run(
        ["age-keygen", "-o", str(path)], check=True, capture_output=True, text=True
    )
    match = re.search(r"# public key: (age1\S+)", path.read_text())
    assert match, f"could not find public key in {path}"
    return match.group(1)


def write_sops_yaml(repo_root: Path, public_key: str) -> None:
    (repo_root / ".sops.yaml").write_text(
        "---\ncreation_rules:\n  - path_regex: secret\\.sops\\.env$\n"
        f"    age: {public_key}\n"
    )


def encrypt_dotenv(path: Path, values: dict[str, str]) -> None:
    """Write plaintext key=value lines to `path` and encrypt it in place.

    Relies on SOPS_AGE_KEY_FILE already being set in the environment and
    the process CWD being inside a tree with a reachable .sops.yaml —
    both of which the `sops_env` fixture in conftest.py sets up.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    subprocess.run(
        ["sops", "-e", "-i", str(path)], check=True, capture_output=True, text=True
    )


def configure_git_identity(path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )


def init_git_repo(path: Path) -> None:
    """Create a fresh git repo at `path` with branch `main` and a test identity."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    configure_git_identity(path)


def git_rev_parse(path: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_commit_all(path: Path, message: str) -> str:
    """Stage everything under `path` and commit it. Returns the new commit sha."""
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", message], check=True)
    return git_rev_parse(path, "HEAD")


def fake_encrypted_dotenv_text(keys: list[str]) -> str:
    """Builds text that passes is_encrypted_dotenv()'s structural check
    without needing real SOPS. The ENC[...] payloads are not real ciphertext
    and cannot actually be decrypted.

    Used in tests that mock decrypt_dotenv() directly, so only the
    structural gate (not the ciphertext) matters.
    """
    lines = [f"{key}=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]" for key in keys]
    lines.append("sops_mac=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]")
    lines.append("sops_version=3.13.3")
    return "\n".join(lines) + "\n"
