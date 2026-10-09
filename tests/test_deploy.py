from __future__ import annotations

import fcntl
import subprocess
from pathlib import Path

import pytest
from conftest import DeployModule, DeployRepo
from helpers import git_commit_all, git_rev_parse


class TestRun:
    def test_wraps_called_process_error(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, ["git"], output="", stderr="boom\n")

        monkeypatch.setattr(deploy_paths.subprocess, "run", fake_run)

        with pytest.raises(deploy_paths.DeployError, match="boom"):
            deploy_paths.run("git", "status")


class TestAllServiceDirs:
    def test_includes_only_dirs_with_compose_yaml_excluding_shared(
        self, deploy_paths: DeployModule
    ) -> None:
        for name in ["zeta", "alpha", "shared", "no_compose"]:
            (deploy_paths.SERVICES_DIR / name).mkdir(parents=True, exist_ok=True)
        (deploy_paths.SERVICES_DIR / "alpha" / "compose.yaml").write_text("")
        (deploy_paths.SERVICES_DIR / "zeta" / "compose.yaml").write_text("")
        (deploy_paths.SERVICES_DIR / "shared" / "compose.yaml").write_text("")

        names = [p.name for p in deploy_paths.all_service_dirs()]

        assert names == ["alpha", "zeta"]

    def test_empty_when_no_services(self, deploy_paths: DeployModule) -> None:
        assert deploy_paths.all_service_dirs() == []

    def test_excludes_deploy_agent_itself(self, deploy_paths: DeployModule) -> None:
        for name in ["alpha", "deploy-agent"]:
            (deploy_paths.SERVICES_DIR / name).mkdir(parents=True, exist_ok=True)
            (deploy_paths.SERVICES_DIR / name / "compose.yaml").write_text("")

        names = [p.name for p in deploy_paths.all_service_dirs()]

        assert names == ["alpha"]


class TestApplyService:
    def test_runs_pull_then_up_with_expected_args(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[list[str], bool | None, Path | None]] = []

        def fake_run(args: list[str], **kwargs: object) -> None:
            calls.append((args, kwargs.get("check"), kwargs.get("cwd")))

        monkeypatch.setattr(deploy_paths.subprocess, "run", fake_run)
        service_dir = deploy_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)

        deploy_paths.apply_service(service_dir)

        assert calls[0] == (
            ["docker", "compose", "--project-directory", str(service_dir), "pull", "--quiet"],
            False,
            None,
        )
        assert calls[1] == (
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
            True,
            deploy_paths.REPO_ROOT,
        )


class TestEnsureNetwork:
    def test_does_nothing_when_network_already_exists(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(deploy_paths.subprocess, "run", fake_run)

        deploy_paths.ensure_network("proxy")

        assert calls == [["docker", "network", "inspect", "proxy"]]

    def test_creates_network_when_missing(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls.append(args)
            returncode = 1 if args[:3] == ["docker", "network", "inspect"] else 0
            return subprocess.CompletedProcess(args, returncode)

        monkeypatch.setattr(deploy_paths.subprocess, "run", fake_run)

        deploy_paths.ensure_network("proxy")

        assert calls == [
            ["docker", "network", "inspect", "proxy"],
            ["docker", "network", "create", "proxy"],
        ]


class TestChangedServiceNames:
    def test_empty_when_local_equals_remote(self, deploy_repo: DeployRepo) -> None:
        module = deploy_repo.module
        head = git_rev_parse(deploy_repo.repo, "HEAD")
        assert module.changed_service_names(head, head) == set()

    def test_reports_only_touched_service_dirs(self, deploy_repo: DeployRepo) -> None:
        module = deploy_repo.module
        before = git_rev_parse(deploy_repo.origin, "HEAD")

        (deploy_repo.origin / "services" / "svc-a").mkdir(parents=True)
        (deploy_repo.origin / "services" / "svc-a" / "compose.yaml").write_text("a")
        after = git_commit_all(deploy_repo.origin, "add svc-a")

        module.run("git", "fetch", "--quiet", "origin", "main")

        assert module.changed_service_names(before, after) == {"svc-a"}


class TestDeploy:
    def _setup_two_services(self, deploy_repo: DeployRepo) -> None:
        for name in ("svc-a", "svc-b"):
            service_dir = deploy_repo.origin / "services" / name
            service_dir.mkdir(parents=True)
            (service_dir / "compose.yaml").write_text(name)
        git_commit_all(deploy_repo.origin, "add services")

    def _record_applied(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        applied: list[str] = []
        monkeypatch.setattr(
            deploy_repo.module,
            "apply_service",
            lambda service_dir: applied.append(service_dir.name),
        )
        monkeypatch.setattr(deploy_repo.module, "prune_images", lambda: None)
        monkeypatch.setattr(deploy_repo.module, "ensure_network", lambda name: None)
        return applied

    def test_bootstraps_newly_added_services(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 0
        assert sorted(applied) == ["svc-a", "svc-b"]

    def test_fast_forwards_local_branch_to_remote(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)

        deploy_repo.module.deploy(force=False)

        assert git_rev_parse(deploy_repo.repo, "HEAD") == git_rev_parse(
            deploy_repo.origin, "HEAD"
        )

    def test_up_to_date_without_force_applies_nothing(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)
        deploy_repo.module.deploy(force=False)
        applied.clear()

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 0
        assert applied == []

    def test_force_applies_every_service_even_when_up_to_date(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)
        deploy_repo.module.deploy(force=False)
        applied.clear()

        rc = deploy_repo.module.deploy(force=True)

        assert rc == 0
        assert sorted(applied) == ["svc-a", "svc-b"]

    def test_only_changed_service_is_applied(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)
        deploy_repo.module.deploy(force=False)
        applied.clear()

        (deploy_repo.origin / "services" / "svc-a" / "compose.yaml").write_text("changed")
        git_commit_all(deploy_repo.origin, "change svc-a")

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 0
        assert applied == ["svc-a"]

    def test_shared_change_applies_every_service(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)
        deploy_repo.module.deploy(force=False)
        applied.clear()

        (deploy_repo.origin / "services" / "shared" / "env" / "base.env").write_text("X=1")
        git_commit_all(deploy_repo.origin, "change shared env")

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 0
        assert sorted(applied) == ["svc-a", "svc-b"]

    def test_one_failing_service_does_not_block_others(
        self,
        deploy_repo: DeployRepo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)

        def flaky_apply(service_dir: Path) -> None:
            if service_dir.name == "svc-a":
                raise subprocess.CalledProcessError(1, ["docker"])
            applied.append(service_dir.name)

        monkeypatch.setattr(deploy_repo.module, "apply_service", flaky_apply)

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 1
        assert applied == ["svc-b"]
        err = capsys.readouterr().err
        assert "svc-a" in err
        assert "ERROR" in err

    def test_decrypt_failure_short_circuits_without_applying(
        self, deploy_repo: DeployRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        applied = self._record_applied(deploy_repo, monkeypatch)
        self._setup_two_services(deploy_repo)
        monkeypatch.setattr(deploy_repo.module.decrypt_secrets, "main", lambda argv: 1)

        rc = deploy_repo.module.deploy(force=False)

        assert rc == 1
        assert applied == []


class TestMain:
    def test_force_flag_is_passed_to_deploy(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        received: dict[str, bool] = {}

        def fake_deploy(force: bool) -> int:
            received["force"] = force
            return 0

        monkeypatch.setattr(deploy_paths, "deploy", fake_deploy)

        assert deploy_paths.main(["--force"]) == 0
        assert received["force"] is True

    def test_defaults_force_to_false(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        received: dict[str, bool] = {}

        def fake_deploy(force: bool) -> int:
            received["force"] = force
            return 0

        monkeypatch.setattr(deploy_paths, "deploy", fake_deploy)

        assert deploy_paths.main([]) == 0
        assert received["force"] is False

    def test_returns_0_and_skips_when_lock_already_held(
        self, deploy_paths: DeployModule
    ) -> None:
        holder = open(deploy_paths.LOCK_FILE, "w")
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            rc = deploy_paths.main([])
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()

        assert rc == 0

    def test_wraps_deploy_error_and_returns_1(
        self,
        deploy_paths: DeployModule,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def boom(force: bool) -> int:
            raise deploy_paths.DeployError("kaboom")

        monkeypatch.setattr(deploy_paths, "deploy", boom)

        rc = deploy_paths.main([])

        assert rc == 1
        assert "kaboom" in capsys.readouterr().err
