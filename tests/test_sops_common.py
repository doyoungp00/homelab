from __future__ import annotations

from pathlib import Path

import pytest
from conftest import requires_sops
from helpers import encrypt_dotenv, fake_encrypted_dotenv_text

from scripts.sops_common import SopsError, is_encrypted_dotenv, run_sops


class TestRunSops:
    def test_raises_sops_error_when_binary_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        def fake_run(*args: object, **kwargs: object) -> None:
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SopsError, match="not installed"):
            run_sops("-d", "whatever")

    def test_raises_sops_error_on_nonzero_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        def fake_run(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, ["sops"], output="", stderr="boom\n")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SopsError, match="boom"):
            run_sops("-d", "whatever")

    @requires_sops
    def test_passes_through_input_and_captures_output(self, tmp_path: Path) -> None:
        # `sops -d` on a nonexistent file writing to stdout is enough to
        # exercise the real subprocess path without needing an age key.
        missing = tmp_path / "nope.env"
        with pytest.raises(SopsError):
            run_sops("-d", str(missing))


class TestIsEncryptedDotenv:
    def test_false_when_file_missing(self, tmp_path: Path) -> None:
        assert is_encrypted_dotenv(tmp_path / "nope.env") is False

    def test_false_for_plain_dotenv(self, tmp_path: Path) -> None:
        path = tmp_path / "plain.env"
        path.write_text("FOO=bar\nBAZ=qux\n")
        assert is_encrypted_dotenv(path) is False

    def test_false_when_missing_mac(self, tmp_path: Path) -> None:
        path = tmp_path / "partial.env"
        path.write_text(
            "FOO=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]\nsops_version=3.13.3\n"
        )
        assert is_encrypted_dotenv(path) is False

    def test_false_when_missing_version(self, tmp_path: Path) -> None:
        path = tmp_path / "partial.env"
        path.write_text(
            "FOO=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]\n"
            "sops_mac=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]\n"
        )
        assert is_encrypted_dotenv(path) is False

    def test_false_when_missing_encrypted_value(self, tmp_path: Path) -> None:
        path = tmp_path / "partial.env"
        path.write_text(
            "sops_mac=ENC[AES256_GCM,data:xx,iv:xx,tag:xx,type:str]\n"
            "sops_version=3.13.3\n"
        )
        assert is_encrypted_dotenv(path) is False

    def test_true_for_structurally_valid_fake(self, tmp_path: Path) -> None:
        path = tmp_path / "fake.env"
        path.write_text(fake_encrypted_dotenv_text(["FOO", "BAR"]))
        assert is_encrypted_dotenv(path) is True

    @requires_sops
    def test_true_for_real_encrypted_file(self, sops_env: Path) -> None:
        path = sops_env / "secret.sops.env"
        encrypt_dotenv(path, {"FOO": "bar"})
        assert is_encrypted_dotenv(path) is True


class TestDecryptDotenv:
    @requires_sops
    def test_round_trips_through_real_sops(self, sops_env: Path) -> None:
        from scripts.sops_common import decrypt_dotenv

        path = sops_env / "secret.sops.env"
        encrypt_dotenv(path, {"FOO": "bar", "BAZ": "qux"})

        plaintext = decrypt_dotenv(path)

        assert "FOO=bar" in plaintext
        assert "BAZ=qux" in plaintext


class TestSetDotenvValue:
    @requires_sops
    def test_updates_single_key_leaving_others_untouched(self, sops_env: Path) -> None:
        from scripts.sops_common import decrypt_dotenv, set_dotenv_value

        path = sops_env / "secret.sops.env"
        encrypt_dotenv(path, {"FOO": "bar", "BAZ": "qux"})

        set_dotenv_value(path, "FOO", "updated")

        plaintext = decrypt_dotenv(path)
        assert "FOO=updated" in plaintext
        assert "BAZ=qux" in plaintext
