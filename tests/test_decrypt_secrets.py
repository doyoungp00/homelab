from __future__ import annotations

import stat
from pathlib import Path

import pytest
from conftest import DecryptSecretsModule, requires_sops
from helpers import encrypt_dotenv

from scripts.sops_common import SopsError


class TestParseDotenv:
    def test_parses_simple_key_values(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        text = "FOO=bar\nBAZ=qux\n"
        assert decrypt_paths.parse_dotenv(text) == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_blank_lines_and_comments(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        text = "\n# a comment\nFOO=bar\n   \n# BAZ=qux\n"
        assert decrypt_paths.parse_dotenv(text) == {"FOO": "bar"}

    def test_skips_lines_without_equals(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        text = "FOO=bar\njustsometext\n"
        assert decrypt_paths.parse_dotenv(text) == {"FOO": "bar"}

    def test_value_may_contain_equals_signs(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        text = "FOO=a=b=c\n"
        assert decrypt_paths.parse_dotenv(text) == {"FOO": "a=b=c"}

    def test_preserves_insertion_order(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        text = "B=2\nA=1\nC=3\n"
        assert list(decrypt_paths.parse_dotenv(text)) == ["B", "A", "C"]


@requires_sops
class TestDecryptForService:
    def test_returns_none_when_nothing_to_decrypt(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        assert decrypt_paths.decrypt_for_service(service_dir) is None

    def test_decrypts_service_only_secret(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(service_dir / "secret.sops.env", {"FOO": "bar"})

        env_path = decrypt_paths.decrypt_for_service(service_dir)

        assert env_path == service_dir / ".env"
        assert env_path.read_text() == "FOO=bar\n"

    def test_merges_shared_and_service_with_service_taking_precedence(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(
            decrypt_paths.SHARED_SECRET, {"SHARED_ONLY": "s", "DUP": "shared"}
        )
        encrypt_dotenv(service_dir / "secret.sops.env", {"OWN": "o", "DUP": "service"})

        env_path = decrypt_paths.decrypt_for_service(service_dir)

        values = decrypt_paths.parse_dotenv(env_path.read_text())
        assert values == {"SHARED_ONLY": "s", "DUP": "service", "OWN": "o"}

    def test_decrypting_shared_env_dir_itself_does_not_double_decrypt(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        encrypt_dotenv(decrypt_paths.SHARED_SECRET, {"FOO": "bar"})

        env_path = decrypt_paths.decrypt_for_service(decrypt_paths.SHARED_ENV_DIR)

        assert env_path == decrypt_paths.SHARED_ENV_DIR / ".env"
        assert env_path.read_text() == "FOO=bar\n"

    def test_written_env_file_has_restrictive_permissions(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(service_dir / "secret.sops.env", {"FOO": "bar"})

        env_path = decrypt_paths.decrypt_for_service(service_dir)

        mode = stat.S_IMODE(env_path.stat().st_mode)
        assert mode == 0o600

    def test_raises_when_secret_file_is_not_actually_encrypted(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / "secret.sops.env").write_text("FOO=bar\n")

        with pytest.raises(SopsError, match="not a SOPS-encrypted"):
            decrypt_paths.decrypt_for_service(service_dir)


class TestAllServiceDirs:
    def test_lists_service_dirs_sorted_excluding_shared(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        for name in ["zeta", "alpha", "shared"]:
            (decrypt_paths.SERVICES_DIR / name).mkdir(parents=True, exist_ok=True)
        (decrypt_paths.SERVICES_DIR / "a_file.txt").write_text("not a dir")

        names = [p.name for p in decrypt_paths.all_service_dirs()]
        assert names == ["alpha", "zeta"]

    def test_empty_when_no_services(self, decrypt_paths: DecryptSecretsModule) -> None:
        assert decrypt_paths.all_service_dirs() == []


@requires_sops
class TestMain:
    def test_services_target_decrypts_named_service(
        self,
        decrypt_paths: DecryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        service_dir = decrypt_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        encrypt_dotenv(service_dir / "secret.sops.env", {"FOO": "bar"})

        rc = decrypt_paths.main(["--services", "svc"])

        assert rc == 0
        assert (service_dir / ".env").read_text() == "FOO=bar\n"

    def test_services_target_reports_missing_directory(
        self,
        decrypt_paths: DecryptSecretsModule,
        sops_env: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = decrypt_paths.main(["--services", "ghost"])

        assert rc == 1
        assert "no such service directory" in capsys.readouterr().err

    def test_shared_target_decrypts_shared_only(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        encrypt_dotenv(decrypt_paths.SHARED_SECRET, {"FOO": "bar"})

        rc = decrypt_paths.main(["--shared"])

        assert rc == 0
        assert (decrypt_paths.SHARED_ENV_DIR / ".env").read_text() == "FOO=bar\n"

    def test_all_services_target_skips_shared_dir(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        svc = decrypt_paths.SERVICES_DIR / "svc"
        svc.mkdir(parents=True)
        encrypt_dotenv(svc / "secret.sops.env", {"FOO": "bar"})
        encrypt_dotenv(decrypt_paths.SHARED_SECRET, {"SHARED": "1"})

        rc = decrypt_paths.main(["--all-services"])

        assert rc == 0
        assert (svc / ".env").is_file()
        assert not (decrypt_paths.SHARED_ENV_DIR / ".env").is_file()

    def test_all_target_decrypts_shared_and_every_service(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        svc = decrypt_paths.SERVICES_DIR / "svc"
        svc.mkdir(parents=True)
        encrypt_dotenv(svc / "secret.sops.env", {"FOO": "bar"})
        encrypt_dotenv(decrypt_paths.SHARED_SECRET, {"SHARED": "1"})

        rc = decrypt_paths.main(["--all"])

        assert rc == 0
        assert (svc / ".env").is_file()
        assert (decrypt_paths.SHARED_ENV_DIR / ".env").is_file()

    def test_continues_past_failed_target_and_returns_nonzero(
        self, decrypt_paths: DecryptSecretsModule, sops_env: Path
    ) -> None:
        good = decrypt_paths.SERVICES_DIR / "good"
        good.mkdir(parents=True)
        encrypt_dotenv(good / "secret.sops.env", {"FOO": "bar"})

        rc = decrypt_paths.main(["--services", "ghost", "good"])

        assert rc == 1
        assert (good / ".env").is_file()

    def test_mutually_exclusive_group_requires_one_option(
        self, decrypt_paths: DecryptSecretsModule
    ) -> None:
        with pytest.raises(SystemExit):
            decrypt_paths.main([])
