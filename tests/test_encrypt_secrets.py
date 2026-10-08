from __future__ import annotations

from pathlib import Path

import pytest
from conftest import EncryptSecretsModule, requires_sops
from helpers import encrypt_dotenv

from scripts.sops_common import SopsError, decrypt_dotenv


class TestParseDotenvAndLoadDotenv:
    def test_parse_dotenv_parses_simple_key_values(
        self, encrypt_paths: EncryptSecretsModule
    ) -> None:
        assert encrypt_paths.parse_dotenv("FOO=bar\nBAZ=qux\n") == {
            "FOO": "bar",
            "BAZ": "qux",
        }

    def test_load_dotenv_returns_empty_dict_when_file_missing(
        self, encrypt_paths: EncryptSecretsModule, tmp_path: Path
    ) -> None:
        assert encrypt_paths.load_dotenv(tmp_path / "nope.env") == {}

    def test_load_dotenv_reads_existing_file(
        self, encrypt_paths: EncryptSecretsModule, tmp_path: Path
    ) -> None:
        path = tmp_path / ".env"
        path.write_text("FOO=bar\n")
        assert encrypt_paths.load_dotenv(path) == {"FOO": "bar"}


@requires_sops
class TestDecrypted:
    def test_returns_empty_dict_when_file_missing(
        self, encrypt_paths: EncryptSecretsModule, tmp_path: Path
    ) -> None:
        assert encrypt_paths.decrypted(tmp_path / "nope.sops.env") == {}

    def test_decrypts_existing_secret(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        path = sops_env / "secret.sops.env"
        encrypt_dotenv(path, {"FOO": "bar"})
        assert encrypt_paths.decrypted(path) == {"FOO": "bar"}

    def test_raises_when_file_is_not_actually_encrypted(
        self, encrypt_paths: EncryptSecretsModule, tmp_path: Path
    ) -> None:
        path = tmp_path / "secret.sops.env"
        path.write_text("FOO=bar\n")
        with pytest.raises(SopsError, match="not a SOPS-encrypted"):
            encrypt_paths.decrypted(path)


@requires_sops
class TestApplyUpdates:
    def test_bootstraps_new_secret_file_when_missing(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        path = sops_env / "new" / "secret.sops.env"

        encrypt_paths.apply_updates(path, {"FOO": "bar"})

        assert path.is_file()
        assert encrypt_paths.decrypted(path) == {"FOO": "bar"}

    def test_sets_values_on_existing_secret_file(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        path = sops_env / "secret.sops.env"
        encrypt_dotenv(path, {"FOO": "bar", "KEEP": "me"})

        encrypt_paths.apply_updates(path, {"FOO": "updated"})

        values = encrypt_paths.decrypted(path)
        assert values == {"FOO": "updated", "KEEP": "me"}


@requires_sops
class TestPushShared:
    def test_no_op_when_env_file_missing(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        encrypt_paths.push_shared()
        assert "nothing to push" in capsys.readouterr().out
        assert not encrypt_paths.SHARED_SECRET.exists()

    def test_bootstraps_shared_secret_from_scratch(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        (encrypt_paths.SHARED_ENV_DIR / ".env").write_text("FOO=bar\n")

        encrypt_paths.push_shared()

        assert encrypt_paths.decrypted(encrypt_paths.SHARED_SECRET) == {"FOO": "bar"}

    def test_pushes_only_changed_keys(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        encrypt_dotenv(encrypt_paths.SHARED_SECRET, {"FOO": "old", "UNCHANGED": "x"})
        (encrypt_paths.SHARED_ENV_DIR / ".env").write_text("FOO=new\nUNCHANGED=x\n")

        encrypt_paths.push_shared()

        assert encrypt_paths.decrypted(encrypt_paths.SHARED_SECRET) == {
            "FOO": "new",
            "UNCHANGED": "x",
        }

    def test_warns_about_orphaned_keys_without_deleting(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        encrypt_dotenv(encrypt_paths.SHARED_SECRET, {"GONE": "x"})
        (encrypt_paths.SHARED_ENV_DIR / ".env").write_text("")

        encrypt_paths.push_shared()

        err = capsys.readouterr().err
        assert "GONE" in err
        assert "WARNING" in err
        assert encrypt_paths.decrypted(encrypt_paths.SHARED_SECRET) == {"GONE": "x"}


@requires_sops
class TestPushForService:
    def test_no_op_when_env_file_missing(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)

        encrypt_paths.push_for_service(service_dir)

        assert "nothing to push" in capsys.readouterr().out

    def test_new_key_not_present_anywhere_is_written_to_own_secret(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / ".env").write_text("NEW=val\n")

        encrypt_paths.push_for_service(service_dir)

        own_secret = service_dir / "secret.sops.env"
        assert encrypt_paths.decrypted(own_secret) == {"NEW": "val"}

    def test_key_already_in_own_secret_is_updated(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        own_secret = service_dir / "secret.sops.env"
        encrypt_dotenv(own_secret, {"FOO": "old"})
        (service_dir / ".env").write_text("FOO=new\n")

        encrypt_paths.push_for_service(service_dir)

        assert encrypt_paths.decrypted(own_secret) == {"FOO": "new"}

    def test_shared_key_unchanged_is_left_alone(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(encrypt_paths.SHARED_SECRET, {"SHARED_KEY": "same"})
        (service_dir / ".env").write_text("SHARED_KEY=same\n")

        encrypt_paths.push_for_service(service_dir)

        own_secret = service_dir / "secret.sops.env"
        assert not own_secret.exists()

    def test_shared_key_changed_becomes_local_override_with_warning(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(encrypt_paths.SHARED_SECRET, {"SHARED_KEY": "orig"})
        (service_dir / ".env").write_text("SHARED_KEY=diverged\n")

        encrypt_paths.push_for_service(service_dir)

        own_secret = service_dir / "secret.sops.env"
        assert encrypt_paths.decrypted(own_secret) == {"SHARED_KEY": "diverged"}
        err = capsys.readouterr().err
        assert "SHARED_KEY" in err
        assert "WARNING" in err

    def test_orphaned_own_key_warns_without_deleting(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        own_secret = service_dir / "secret.sops.env"
        encrypt_dotenv(own_secret, {"GONE": "x"})
        (service_dir / ".env").write_text("")

        encrypt_paths.push_for_service(service_dir)

        err = capsys.readouterr().err
        assert "GONE" in err
        assert "WARNING" in err
        assert encrypt_paths.decrypted(own_secret) == {"GONE": "x"}


class TestAllServiceDirs:
    def test_lists_service_dirs_sorted_excluding_shared(
        self, encrypt_paths: EncryptSecretsModule
    ) -> None:
        for name in ["zeta", "alpha", "shared"]:
            (encrypt_paths.SERVICES_DIR / name).mkdir(parents=True, exist_ok=True)

        names = [p.name for p in encrypt_paths.all_service_dirs()]
        assert names == ["alpha", "zeta"]


@requires_sops
class TestMain:
    def test_services_target_pushes_named_service(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = encrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / ".env").write_text("FOO=bar\n")

        rc = encrypt_paths.main(["--services", "svc"])

        assert rc == 0
        assert encrypt_paths.decrypted(service_dir / "secret.sops.env") == {
            "FOO": "bar"
        }

    def test_shared_target_pushes_shared_only(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        (encrypt_paths.SHARED_ENV_DIR / ".env").write_text("FOO=bar\n")

        rc = encrypt_paths.main(["--shared"])

        assert rc == 0
        assert encrypt_paths.decrypted(encrypt_paths.SHARED_SECRET) == {"FOO": "bar"}

    def test_all_target_pushes_shared_then_every_service(
        self, encrypt_paths: EncryptSecretsModule, sops_env: Path
    ) -> None:
        (encrypt_paths.SHARED_ENV_DIR / ".env").write_text("SHARED=1\n")
        svc = encrypt_paths.SERVICES_DIR / "svc"
        svc.mkdir(parents=True)
        (svc / ".env").write_text("FOO=bar\n")

        rc = encrypt_paths.main(["--all"])

        assert rc == 0
        assert encrypt_paths.decrypted(encrypt_paths.SHARED_SECRET) == {"SHARED": "1"}
        assert encrypt_paths.decrypted(svc / "secret.sops.env") == {"FOO": "bar"}

    def test_services_target_reports_missing_directory(
        self,
        encrypt_paths: EncryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = encrypt_paths.main(["--services", "ghost"])

        assert rc == 1
        assert "no such service directory" in capsys.readouterr().err

    def test_mutually_exclusive_group_requires_one_option(
        self, encrypt_paths: EncryptSecretsModule
    ) -> None:
        with pytest.raises(SystemExit):
            encrypt_paths.main([])
