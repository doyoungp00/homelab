from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest
from helpers import (
    AGE_KEYGEN_AVAILABLE,
    SOPS_AVAILABLE,
    configure_git_identity,
    generate_age_key,
    git_commit_all,
    init_git_repo,
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


class DeployModule(Protocol):
    """Structural shape of `scripts.deploy` as used by its tests.
    See `DecryptSecretsModule` for why this exists."""

    REPO_ROOT: Path
    SERVICES_DIR: Path
    LOCK_FILE: Path
    BRANCH: str
    SELF_SERVICE_NAME: str

    class DeployError(RuntimeError): ...

    def run(self, *args: str) -> str: ...
    def changed_service_names(self, local: str, remote: str) -> set[str]: ...
    def apply_service(self, service_dir: Path) -> None: ...
    def prune_images(self) -> None: ...
    def ensure_network(self, name: str) -> None: ...
    def all_service_dirs(self) -> list[Path]: ...
    def deploy(self, force: bool, only_service: str | None = None) -> int: ...
    def main(self, argv: list[str]) -> int: ...


@pytest.fixture
def deploy_paths(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> DeployModule:
    """Point deploy's module-level path constants at tmp_repo, with no git
    repo involved. Use this for tests that don't need real fetch/merge."""
    from scripts import deploy

    monkeypatch.setattr(deploy, "REPO_ROOT", tmp_repo)
    monkeypatch.setattr(deploy, "SERVICES_DIR", tmp_repo / "services")
    monkeypatch.setattr(deploy, "BRANCH", "main")
    monkeypatch.setattr(deploy, "LOCK_FILE", tmp_repo / "deploy.lock")
    return deploy


@dataclass
class DeployRepo:
    """A real `origin` repo plus a clone of it wired up as scripts.deploy's
    REPO_ROOT. Tests commit new changes into `origin` to simulate upstream
    pushes, then call `module.deploy(...)` on the `repo` clone."""

    module: DeployModule
    origin: Path
    repo: Path


@pytest.fixture
def deploy_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DeployRepo:
    from scripts import deploy

    origin = tmp_path / "origin"
    init_git_repo(origin)
    (origin / "services" / "shared" / "env").mkdir(parents=True)
    (origin / "services" / "shared" / "env" / ".gitkeep").write_text("")
    git_commit_all(origin, "init")

    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True)
    configure_git_identity(repo)

    monkeypatch.setattr(deploy, "REPO_ROOT", repo)
    monkeypatch.setattr(deploy, "SERVICES_DIR", repo / "services")
    monkeypatch.setattr(deploy, "BRANCH", "main")
    monkeypatch.setattr(deploy, "LOCK_FILE", tmp_path / "deploy.lock")
    # Deploy's own decrypt step is out of scope here and must never touch
    # the real repo's secrets; tests that care about it override this.
    monkeypatch.setattr(deploy.decrypt_secrets, "main", lambda argv: 0)

    return DeployRepo(module=deploy, origin=origin, repo=repo)


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
