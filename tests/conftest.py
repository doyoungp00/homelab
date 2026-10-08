from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest
from helpers import (
    AGE_KEYGEN_AVAILABLE,
    SOPS_AVAILABLE,
    generate_age_key,
    write_sops_yaml,
)

requires_sops = pytest.mark.skipif(
    not (SOPS_AVAILABLE and AGE_KEYGEN_AVAILABLE),
    reason="sops and age-keygen must both be on PATH for this test",
)


class DecryptSecretsModule(Protocol):
    """Structural shape of `scripts.decrypt_secrets` as used by its tests.

    `decrypt_paths` hands back the real module (with its path constants
    monkeypatched), so this Protocol exists purely to give that fixture
    a type pytest fixtures can't declare any other way — a module object
    can't be used as a type annotation directly.
    """

    SERVICES_DIR: Path
    SHARED_ENV_DIR: Path
    SHARED_SECRET: Path

    def parse_dotenv(self, text: str) -> dict[str, str]: ...
    def decrypt_for_service(self, service_dir: Path) -> Path | None: ...
    def main(self, argv: list[str]) -> int: ...


class EncryptSecretsModule(Protocol):
    """Structural shape of `scripts.encrypt_secrets` as used by its tests.
    See `DecryptSecretsModule` for why this exists."""

    SERVICES_DIR: Path
    SHARED_ENV_DIR: Path
    SHARED_SECRET: Path

    def parse_dotenv(self, text: str) -> dict[str, str]: ...
    def load_dotenv(self, path: Path) -> dict[str, str]: ...
    def decrypted(self, path: Path) -> dict[str, str]: ...
    def apply_updates(self, secret_path: Path, updates: dict[str, str]) -> None: ...
    def push_shared(self) -> None: ...
    def push_for_service(self, service_dir: Path) -> None: ...
    def main(self, argv: list[str]) -> int: ...


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A disposable repo skeleton: <tmp>/services/shared/env/."""
    (tmp_path / "services" / "shared" / "env").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def decrypt_paths(
    tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> DecryptSecretsModule:
    """Point decrypt_secrets' module-level path constants at tmp_repo."""
    from scripts import decrypt_secrets

    services_dir = tmp_repo / "services"
    shared_env_dir = services_dir / "shared" / "env"
    monkeypatch.setattr(decrypt_secrets, "REPO_ROOT", tmp_repo)
    monkeypatch.setattr(decrypt_secrets, "SERVICES_DIR", services_dir)
    monkeypatch.setattr(decrypt_secrets, "SHARED_ENV_DIR", shared_env_dir)
    monkeypatch.setattr(
        decrypt_secrets, "SHARED_SECRET", shared_env_dir / "secret.sops.env"
    )
    return decrypt_secrets


@pytest.fixture
def encrypt_paths(
    tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> EncryptSecretsModule:
    """Point encrypt_secrets' module-level path constants at tmp_repo."""
    from scripts import encrypt_secrets

    services_dir = tmp_repo / "services"
    shared_env_dir = services_dir / "shared" / "env"
    monkeypatch.setattr(encrypt_secrets, "REPO_ROOT", tmp_repo)
    monkeypatch.setattr(encrypt_secrets, "SERVICES_DIR", services_dir)
    monkeypatch.setattr(encrypt_secrets, "SHARED_ENV_DIR", shared_env_dir)
    monkeypatch.setattr(
        encrypt_secrets, "SHARED_SECRET", shared_env_dir / "secret.sops.env"
    )
    return encrypt_secrets


@pytest.fixture
def sops_env(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A disposable age key + .sops.yaml for tmp_repo, with
    SOPS_AGE_KEY_FILE set and CWD moved into tmp_repo.

    sops discovers .sops.yaml by walking up from the CWD, not from the
    target file's path, so the chdir is required — without it, sops
    would walk up from the real homelab/ checkout and pick up the real
    .sops.yaml and age key instead of this fixture's.
    """
    key_path = tmp_repo / "age.key"
    public_key = generate_age_key(key_path)
    write_sops_yaml(tmp_repo, public_key)
    monkeypatch.setenv("SOPS_AGE_KEY_FILE", str(key_path))
    monkeypatch.chdir(tmp_repo)
    return tmp_repo
