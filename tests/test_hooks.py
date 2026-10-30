from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from conftest import DeployModule

from scripts import hooks


@pytest.fixture(autouse=True)
def clear_module_cache() -> None:
    """hooks caches imported modules per path for the life of a deploy run.
    Tests reuse tmp paths, so a stale entry would leak between them."""
    hooks._MODULES.clear()


@pytest.fixture
def appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "appdata"
    root.mkdir()
    monkeypatch.setenv("APPDATA_DIR", str(root))
    monkeypatch.delenv("MNT_APPDATA", raising=False)
    return root


def write_hook(service_dir: Path, body: str) -> Path:
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "hooks.py").write_text(body)
    return service_dir


def fire(service_dir: Path, phase: str = "pre_deploy") -> bool:
    return hooks.fire(phase, service_dir, proxy_subnet="10.9.0.0/24", run=lambda *a: "")


class TestAppdataRoot:
    def test_prefers_appdata_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPDATA_DIR", "/appdata")
        monkeypatch.setenv("MNT_APPDATA", "/mnt/host")

        assert hooks.appdata_root() == Path("/appdata")

    def test_falls_back_to_mnt_appdata_when_run_on_the_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("APPDATA_DIR", raising=False)
        monkeypatch.setenv("MNT_APPDATA", "/mnt/host")

        assert hooks.appdata_root() == Path("/mnt/host")

    def test_raises_when_neither_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APPDATA_DIR", raising=False)
        monkeypatch.delenv("MNT_APPDATA", raising=False)

        with pytest.raises(hooks.HookError, match="APPDATA_DIR"):
            hooks.appdata_root()


class TestFire:
    def test_service_without_hooks_file_is_a_no_op(self, tmp_path: Path) -> None:
        (tmp_path / "svc").mkdir()

        assert fire(tmp_path / "svc") is False

    def test_hooks_file_without_that_phase_is_a_no_op(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(tmp_path / "svc", "def post_deploy(ctx):\n    return True\n")

        assert fire(svc, "pre_deploy") is False

    def test_returns_whether_the_hook_reported_a_change(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        changed = write_hook(tmp_path / "a", "def pre_deploy(ctx):\n    return True\n")
        unchanged = write_hook(tmp_path / "b", "def pre_deploy(ctx):\n    return False\n")

        assert fire(changed) is True
        assert fire(unchanged) is False

    def test_a_hook_returning_none_counts_as_unchanged(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(tmp_path / "svc", "def pre_deploy(ctx):\n    pass\n")

        assert fire(svc) is False

    def test_hook_exception_becomes_a_hook_error_naming_service_and_phase(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(tmp_path / "svc", "def pre_deploy(ctx):\n    raise ValueError('nope')\n")

        with pytest.raises(hooks.HookError, match=r"svc: pre_deploy raised ValueError: nope"):
            fire(svc)

    def test_import_error_becomes_a_hook_error(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(tmp_path / "svc", "import nonexistent_module_xyz\n")

        with pytest.raises(hooks.HookError, match="failed to import"):
            fire(svc)

    def test_context_scopes_appdata_to_the_service(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(
            tmp_path / "svc",
            "def pre_deploy(ctx):\n"
            "    (ctx.appdata / 'marker').parent.mkdir(parents=True, exist_ok=True)\n"
            "    (ctx.appdata / 'marker').write_text(ctx.name + ' ' + ctx.proxy_subnet)\n"
            "    return True\n",
        )

        fire(svc)

        assert (appdata / "svc" / "marker").read_text() == "svc 10.9.0.0/24"

    def test_module_is_imported_once_across_phases(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = write_hook(
            tmp_path / "svc",
            "COUNTER = []\n"
            "COUNTER.append(1)\n"
            "def pre_deploy(ctx):\n    return False\n"
            "def post_deploy(ctx):\n    return False\n",
        )

        fire(svc, "pre_deploy")
        fire(svc, "post_deploy")

        assert len(hooks.load(svc).COUNTER) == 1


class TestContextHelpers:
    def context(self, tmp_path: Path, appdata: Path) -> hooks.Context:
        service_dir = tmp_path / "svc"
        service_dir.mkdir(exist_ok=True)
        return hooks.Context(
            name="svc",
            service_dir=service_dir,
            appdata=appdata / "svc",
            proxy_subnet="10.9.0.0/24",
            run=lambda *a: "",
        )

    def test_write_if_changed_creates_missing_parents(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        ctx = self.context(tmp_path, appdata)

        assert ctx.write_if_changed(ctx.appdata / "deep/nested/file", "hi") is True
        assert (ctx.appdata / "deep/nested/file").read_text() == "hi"

    def test_write_if_changed_is_false_for_identical_content(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        ctx = self.context(tmp_path, appdata)
        ctx.write_if_changed(ctx.appdata / "f", "hi")

        assert ctx.write_if_changed(ctx.appdata / "f", "hi") is False
        assert ctx.write_if_changed(ctx.appdata / "f", "bye") is True

    def test_sync_overwrites_drift(self, tmp_path: Path, appdata: Path) -> None:
        ctx = self.context(tmp_path, appdata)
        (ctx.service_dir / "acquis.yaml").write_text("from repo\n")
        ctx.appdata.mkdir(parents=True)
        (ctx.appdata / "acquis.yaml").write_text("edited by hand\n")

        assert ctx.sync("acquis.yaml") is True
        assert (ctx.appdata / "acquis.yaml").read_text() == "from repo\n"
        assert ctx.sync("acquis.yaml") is False

    def test_sync_can_rename(self, tmp_path: Path, appdata: Path) -> None:
        ctx = self.context(tmp_path, appdata)
        (ctx.service_dir / "src.yaml").write_text("x\n")

        assert ctx.sync("src.yaml", "nested/dst.yaml") is True
        assert (ctx.appdata / "nested/dst.yaml").read_text() == "x\n"

    def test_seed_writes_only_when_target_is_absent(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        ctx = self.context(tmp_path, appdata)
        (ctx.service_dir / "data").mkdir()
        (ctx.service_dir / "data/config.yaml").write_text("starter\n")

        assert ctx.seed("data/config.yaml", "config/config.yaml") is True
        (ctx.appdata / "config/config.yaml").write_text("user edited\n")

        assert ctx.seed("data/config.yaml", "config/config.yaml") is False
        assert (ctx.appdata / "config/config.yaml").read_text() == "user edited\n"


class TestHomeAssistantHook:
    """The real hook, not a stand-in: its fresh-host branch is the one that
    only ever runs once per NAS rebuild, so it gets no exercise in practice."""

    def hook(self, tmp_path: Path, appdata: Path):
        service_dir = tmp_path / "homeassistant"
        service_dir.mkdir()
        real = Path(__file__).resolve().parent.parent / "services/homeassistant/hooks.py"
        (service_dir / "hooks.py").write_text(real.read_text())
        return service_dir

    def storage(self, appdata: Path) -> Path:
        return appdata / "homeassistant/config/.storage/http"

    def test_seeds_a_usable_storage_key_when_ha_has_never_booted(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, appdata)

        assert fire(svc) is True

        data = json.loads(self.storage(appdata).read_text())
        assert data["key"] == "http"
        assert data["data"]["stable"]["trusted_proxies"] == ["10.9.0.0/24"]
        assert data["data"]["stable"]["use_x_forwarded_for"] is True
        # Pinned so HA 2026.8's port-80 default can't break the Traefik route.
        assert data["data"]["stable"]["server_port"] == 8123
        # Without this HA's migration pass overwrites the above on first boot.
        assert data["data"]["yaml_migration_done"] is True

    def test_seeded_host_needs_no_second_deploy(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, appdata)
        fire(svc)

        # The merge branch now sees its own seed and finds nothing to do —
        # the bug was that this took two deploys to reach.
        assert fire(svc) is False

    def test_merges_into_an_existing_file_without_touching_other_keys(
        self, tmp_path: Path, appdata: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = self.hook(tmp_path, appdata)
        path = self.storage(appdata)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "key": "http",
                    "data": {
                        "stable": {"server_port": 8123, "ssl_profile": "modern"},
                        "pending": None,
                    },
                }
            )
        )

        assert hooks.fire(
            "pre_deploy", svc, proxy_subnet="10.9.0.0/24", run=lambda *a: ""
        ) is True

        stable = json.loads(path.read_text())["data"]["stable"]
        assert stable["trusted_proxies"] == ["10.9.0.0/24"]
        assert stable["ssl_profile"] == "modern"

    def test_does_nothing_when_already_correct(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, appdata)
        path = self.storage(appdata)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "data": {
                        "stable": {
                            "use_x_forwarded_for": True,
                            "trusted_proxies": ["10.9.0.0/24"],
                        }
                    }
                }
            )
        )
        before = path.read_text()

        assert fire(svc) is False
        assert path.read_text() == before

    def test_stops_the_container_before_writing_over_a_live_file(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, appdata)
        path = self.storage(appdata)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"data": {"stable": {"server_port": 8123}}}))

        commands: list[tuple[str, ...]] = []

        def fake_run(*args: str) -> str:
            commands.append(args)
            return "container-id" if args[1] == "ps" else ""

        hooks.fire("pre_deploy", svc, proxy_subnet="10.9.0.0/24", run=fake_run)

        assert commands[-1] == ("docker", "stop", "homeassistant")

    def test_does_not_stop_a_container_it_is_not_changing(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, appdata)
        path = self.storage(appdata)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "data": {
                        "stable": {
                            "use_x_forwarded_for": True,
                            "trusted_proxies": ["10.9.0.0/24"],
                        }
                    }
                }
            )
        )

        commands: list[tuple[str, ...]] = []
        hooks.fire(
            "pre_deploy",
            svc,
            proxy_subnet="10.9.0.0/24",
            run=lambda *a: commands.append(a) or "",
        )

        assert commands == []


class TestHomepageHook:
    """The real hook. The overlay path is the interesting one: it is the only
    mechanism keeping machine-local config out of the repo, and nothing else
    would catch it silently appending to the wrong file."""

    def hook(self, tmp_path: Path, public: dict[str, str]):
        service_dir = tmp_path / "homepage"
        (service_dir / "config").mkdir(parents=True)
        real = Path(__file__).resolve().parent.parent / "services/homepage/hooks.py"
        (service_dir / "hooks.py").write_text(real.read_text())
        for name, text in public.items():
            (service_dir / "config" / name).write_text(text)
        return service_dir

    def test_copies_public_config_verbatim_when_no_overlay_exists(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, {"services.yaml": "---\n- Media:\n"})

        assert fire(svc) is True
        assert (appdata / "homepage/config/services.yaml").read_text() == "---\n- Media:\n"

    def test_appends_the_local_overlay(self, tmp_path: Path, appdata: Path) -> None:
        svc = self.hook(tmp_path, {"services.yaml": "---\n- Media:\n"})
        overlay = appdata / "homepage/local/services.yaml"
        overlay.parent.mkdir(parents=True)
        overlay.write_text("- Surveillance:\n      - Living room:\n")

        fire(svc)

        result = (appdata / "homepage/config/services.yaml").read_text()
        assert result == "---\n- Media:\n\n- Surveillance:\n      - Living room:\n"
        # One YAML document, so Homepage sees both groups.
        assert result.count("---") == 1

    def test_overlay_is_per_file(self, tmp_path: Path, appdata: Path) -> None:
        svc = self.hook(
            tmp_path, {"services.yaml": "---\n- Media:\n", "custom.css": "a {}\n"}
        )
        overlay = appdata / "homepage/local/custom.css"
        overlay.parent.mkdir(parents=True)
        overlay.write_text("b {}\n")

        fire(svc)

        assert (appdata / "homepage/config/custom.css").read_text() == "a {}\n\nb {}\n"
        assert (appdata / "homepage/config/services.yaml").read_text() == "---\n- Media:\n"

    def test_copies_images_byte_exact(self, tmp_path: Path, appdata: Path) -> None:
        svc = self.hook(tmp_path, {"settings.yaml": "---\n"})
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + bytes(range(256))
        (svc / "images").mkdir()
        (svc / "images/bg.jpg").write_bytes(jpeg)

        assert fire(svc) is True
        assert (appdata / "homepage/images/bg.jpg").read_bytes() == jpeg
        # No overlay is appended to a binary — that would corrupt it.
        assert fire(svc) is False

    def test_images_are_optional(self, tmp_path: Path, appdata: Path) -> None:
        svc = self.hook(tmp_path, {"settings.yaml": "---\n"})

        assert fire(svc) is True
        assert not (appdata / "homepage/images").exists()

    def test_leaves_nas_only_images_alone(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, {"settings.yaml": "---\n"})
        (svc / "images").mkdir()
        (svc / "images/bg.jpg").write_bytes(b"\xff\xd8public")
        private = appdata / "homepage/images/private.jpg"
        private.parent.mkdir(parents=True)
        private.write_bytes(b"\xff\xd8private")

        fire(svc)

        assert private.read_bytes() == b"\xff\xd8private"

    def test_is_a_no_op_once_everything_matches(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path, {"services.yaml": "---\n", "custom.css": "a {}\n"})
        fire(svc)

        assert fire(svc) is False

    def test_reports_a_change_even_when_an_earlier_file_already_matched(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        # `or` instead of `|=` would short-circuit here and leave custom.css
        # unwritten, because services.yaml already matches.
        svc = self.hook(tmp_path, {"aaa.yaml": "one\n", "zzz.css": "two\n"})
        fire(svc)
        (svc / "config/zzz.css").write_text("changed\n")

        assert fire(svc) is True
        assert (appdata / "homepage/config/zzz.css").read_text() == "changed\n"


GLUETUN_ID = "a" * 64
STALE_ID = "b" * 64
SHARERS = ("prowlarr", "qbittorrent", "suwayomi-server")


class TestArrStackHook:
    """The real hook. It repairs a failure that is invisible from outside —
    containers that are up and healthy with a dead network namespace — so
    neither firing when it should nor firing when it shouldn't would be
    noticed by anything else."""

    def hook(self, tmp_path: Path) -> Path:
        service_dir = tmp_path / "arr-stack"
        service_dir.mkdir()
        real = Path(__file__).resolve().parent.parent / "services/arr-stack/hooks.py"
        (service_dir / "hooks.py").write_text(real.read_text())
        return service_dir

    def fire(
        self, svc: Path, modes: dict[str, str], gluetun_id: str = GLUETUN_ID
    ) -> tuple[bool, list[tuple[str, ...]]]:
        """Run post_deploy against a stand-in docker.

        `modes` maps a container name to its HostConfig.NetworkMode. A name
        missing from it is a container that doesn't exist on the host.
        """
        commands: list[tuple[str, ...]] = []

        def fake_run(*args: str) -> str:
            commands.append(args)
            if args[1] == "ps":
                name = args[-1].removeprefix("name=^").removesuffix("$")
                if name == "gluetun":
                    return gluetun_id
                return "c" * 64 if name in modes else ""
            if args[1] == "inspect":
                return modes[args[-1]]
            return ""

        changed = hooks.fire(
            "post_deploy", svc, proxy_subnet="10.9.0.0/24", run=fake_run
        )
        return changed, commands

    def test_recreates_only_what_is_left_on_a_replaced_gluetun(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path)

        changed, commands = self.fire(
            svc,
            {
                "prowlarr": f"container:{STALE_ID}",
                "qbittorrent": f"container:{GLUETUN_ID}",
                "suwayomi-server": f"container:{STALE_ID}",
            },
        )

        assert changed is True
        assert commands[-1][:2] == ("docker", "compose")
        assert commands[-1][-2:] == ("prowlarr", "suwayomi-server")

    def test_recreate_leaves_gluetun_itself_alone(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        # Without --no-deps, `up prowlarr` brings depends_on along and
        # force-recreating gluetun hands it a third id, invalidating the
        # namespace this call just repaired.
        svc = self.hook(tmp_path)

        _, commands = self.fire(svc, {"prowlarr": f"container:{STALE_ID}"})

        assert "--no-deps" in commands[-1]
        assert "--force-recreate" in commands[-1]
        assert "gluetun" not in commands[-1]

    def test_is_a_no_op_when_every_container_is_current(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path)

        changed, commands = self.fire(
            svc, {name: f"container:{GLUETUN_ID}" for name in SHARERS}
        )

        assert changed is False
        assert all(cmd[1] != "compose" for cmd in commands)

    def test_a_short_id_counts_as_current(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path)

        changed, _ = self.fire(
            svc, {name: f"container:{GLUETUN_ID[:12]}" for name in SHARERS}
        )

        assert changed is False

    def test_the_name_form_counts_as_current(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        # If compose ever resolves to `container:gluetun` rather than an id,
        # docker re-resolves on start and nothing needs repairing. Reading
        # that as drift would bounce three containers on every deploy.
        svc = self.hook(tmp_path)

        changed, _ = self.fire(svc, {name: "container:gluetun" for name in SHARERS})

        assert changed is False

    def test_a_container_that_does_not_exist_is_skipped_not_inspected(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path)

        changed, commands = self.fire(svc, {"prowlarr": f"container:{STALE_ID}"})

        assert changed is True
        assert commands[-1][-1] == "prowlarr"
        assert not any(
            cmd[1] == "inspect" and cmd[-1] == "qbittorrent" for cmd in commands
        )

    def test_does_nothing_at_all_when_gluetun_is_missing(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        svc = self.hook(tmp_path)

        changed, commands = self.fire(
            svc, {name: f"container:{STALE_ID}" for name in SHARERS}, gluetun_id=""
        )

        assert changed is False
        assert len(commands) == 1


class TestFirefoxHook:
    """Same repair as arr-stack's, against its own gluetun. Pointing it at
    arr-stack's would compare against the wrong id and bounce firefox on
    every deploy, or never repair it."""

    def test_rejoins_firefox_to_its_own_gluetun(
        self, tmp_path: Path, appdata: Path
    ) -> None:
        service_dir = tmp_path / "firefox"
        service_dir.mkdir()
        real = Path(__file__).resolve().parent.parent / "services/firefox/hooks.py"
        (service_dir / "hooks.py").write_text(real.read_text())
        commands: list[tuple[str, ...]] = []

        def fake_run(*args: str) -> str:
            commands.append(args)
            if args[1] == "ps":
                name = args[-1].removeprefix("name=^").removesuffix("$")
                return {"firefox-gluetun": GLUETUN_ID, "firefox": "c" * 64}.get(name, "")
            if args[1] == "inspect":
                return f"container:{STALE_ID}"
            return ""

        changed = hooks.fire(
            "post_deploy", service_dir, proxy_subnet="10.9.0.0/24", run=fake_run
        )

        assert changed is True
        assert commands[0][-1] == "name=^firefox-gluetun$"
        assert commands[-1][-1] == "firefox"


class TestDeployIntegration:
    def run_apply(
        self,
        deploy_paths: DeployModule,
        monkeypatch: pytest.MonkeyPatch,
        hook_body: str | None,
    ) -> list[list[str]]:
        calls: list[list[str]] = []
        monkeypatch.setattr(
            deploy_paths.subprocess, "run", lambda args, **kw: calls.append(args)
        )

        service_dir = deploy_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / "compose.yaml").write_text("services:\n  svc:\n    image: foo\n")
        if hook_body is not None:
            (service_dir / "hooks.py").write_text(hook_body)

        deploy_paths.apply_service(service_dir)
        return calls

    def test_changed_pre_deploy_forces_recreate_of_an_image_service(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch, appdata: Path
    ) -> None:
        calls = self.run_apply(
            deploy_paths, monkeypatch, "def pre_deploy(ctx):\n    return True\n"
        )

        assert "--force-recreate" in calls[-1]

    def test_unchanged_pre_deploy_leaves_the_container_alone(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch, appdata: Path
    ) -> None:
        calls = self.run_apply(
            deploy_paths, monkeypatch, "def pre_deploy(ctx):\n    return False\n"
        )

        assert "--force-recreate" not in calls[-1]

    def test_pre_deploy_runs_before_compose_and_post_deploy_after(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch, appdata: Path
    ) -> None:
        order: list[str] = []
        monkeypatch.setattr(
            deploy_paths.subprocess,
            "run",
            lambda args, **kw: order.append(" ".join(args[4:6])),
        )
        service_dir = deploy_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / "compose.yaml").write_text("services:\n  svc:\n    image: foo\n")
        (service_dir / "hooks.py").write_text(
            f"import pathlib\n"
            f"LOG = pathlib.Path({str(deploy_paths.REPO_ROOT / 'order')!r})\n"
            "def pre_deploy(ctx):\n"
            "    LOG.write_text('pre\\n')\n"
            "    return False\n"
            "def post_deploy(ctx):\n"
            "    LOG.write_text(LOG.read_text() + 'post\\n')\n"
            "    return False\n"
        )

        # Record hook ordering relative to the compose calls by appending to
        # the same list the subprocess stub writes to.
        original = deploy_paths.hooks.fire

        def traced(phase: str, *args: object, **kwargs: object) -> bool:
            order.append(phase)
            return original(phase, *args, **kwargs)

        monkeypatch.setattr(deploy_paths.hooks, "fire", traced)
        deploy_paths.apply_service(service_dir)

        assert order == ["pre_deploy", "pull --quiet", "up -d", "post_deploy"]

    def test_failing_hook_skips_compose_entirely(
        self, deploy_paths: DeployModule, monkeypatch: pytest.MonkeyPatch, appdata: Path
    ) -> None:
        calls: list[list[str]] = []
        monkeypatch.setattr(
            deploy_paths.subprocess, "run", lambda args, **kw: calls.append(args)
        )
        service_dir = deploy_paths.SERVICES_DIR / "svc"
        service_dir.mkdir(parents=True)
        (service_dir / "compose.yaml").write_text("services:\n  svc:\n    image: foo\n")
        (service_dir / "hooks.py").write_text(
            "def pre_deploy(ctx):\n    raise RuntimeError('bad config')\n"
        )

        with pytest.raises(hooks.HookError):
            deploy_paths.apply_service(service_dir)

        assert calls == []


class TestAuthentikHook:
    """The real hook. Its ownership fix only matters on a host whose ACL hides
    root-written files, which nothing else here would notice."""

    def hook(self, tmp_path: Path) -> Path:
        service_dir = tmp_path / "authentik"
        (service_dir / "blueprints").mkdir(parents=True)
        real = Path(__file__).resolve().parent.parent / "services/authentik/hooks.py"
        (service_dir / "hooks.py").write_text(real.read_text())
        (service_dir / "blueprints/groups.yaml").write_text("version: 1\n")
        return service_dir

    def test_hands_blueprints_to_the_authentik_user(
        self, tmp_path: Path, appdata: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chowned: list[tuple[str, int, int]] = []
        monkeypatch.setattr(
            "os.chown", lambda path, uid, gid: chowned.append((Path(path).name, uid, gid))
        )
        svc = self.hook(tmp_path)
        # Anyone but the test runner, so the files read as wrongly owned
        # whatever UID runs the suite.
        target = os.getuid() + 1
        monkeypatch.setattr(hooks.load(svc), "AUTHENTIK_UID", target)

        changed = hooks.fire("pre_deploy", svc, proxy_subnet="", run=lambda *a: "")

        assert changed is False
        assert (appdata / "authentik/blueprints/groups.yaml").read_text() == "version: 1\n"
        assert sorted(chowned) == [("blueprints", target, target), ("groups.yaml", target, target)]

    def test_removes_blueprints_deleted_from_the_repo(
        self, tmp_path: Path, appdata: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("os.chown", lambda *a: None)
        stale = appdata / "authentik/blueprints/old.yaml"
        stale.parent.mkdir(parents=True)
        stale.write_text("version: 1\n")

        hooks.fire("pre_deploy", self.hook(tmp_path), proxy_subnet="", run=lambda *a: "")

        assert not stale.exists()
