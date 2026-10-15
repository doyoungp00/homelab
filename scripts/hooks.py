"""Per-service deploy hooks: `services/<name>/hooks.py`, run around `compose up`.

Some services need files placed under their appdata bind mount before the
container reads them — config the image has no way to generate, or settings
that depend on how the stack is wired rather than on user preference. A hook
is plain Python in the service's own directory:

    # services/crowdsec/hooks.py
    def pre_deploy(ctx):
        return ctx.sync("acquis.yaml")

Both `pre_deploy(ctx)` and `post_deploy(ctx)` are optional. Living inside the
service directory is not just tidiness: `deploy.changed_service_names()` diffs
whole service directories, so editing a hook already redeploys exactly the
service it belongs to, with no extra wiring.

**A truthy return from pre_deploy means "I changed something on disk"**, which
makes `apply_service` add `--force-recreate`. This matters because `compose up`
decides whether to recreate by hashing the resolved compose config — it has no
idea a hook rewrote a file the container only reads at startup. Without the
flag, config written by a hook would sit unread until something unrelated
changed. The corollary is that hooks must be honest about no-ops, or every
deploy restarts every hooked service; `write_if_changed` and friends return
the right thing for free. post_deploy runs after the container is up, where
there is nothing left to recreate, so its return value is only logged.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

HOOKS_FILENAME = "hooks.py"
PHASES = ("pre_deploy", "post_deploy")


class HookError(RuntimeError):
    """Raised when a hook can't be loaded or raises while running."""


@dataclass(frozen=True)
class Context:
    """What a hook is handed. Deliberately small.

    `appdata` is scoped to the one service, so the ordinary path can't reach a
    neighbour's data by accident. It's convenience, not a sandbox — a hook is
    arbitrary Python and deploy-agent mounts the whole appdata tree.
    """

    name: str
    service_dir: Path
    appdata: Path
    proxy_subnet: str
    run: Callable[..., str]

    def write_if_changed(self, path: Path, content: str) -> bool:
        """Write `content` to `path` only if it differs. True if written."""
        if path.is_file() and path.read_text() == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return True

    def sync(self, src: str, dst: str | None = None) -> bool:
        """Repo owns this file: overwrite appdata's copy whenever it drifts.

        `src` is relative to the service directory, `dst` to its appdata
        directory (defaulting to the same relative path).
        """
        return self.write_if_changed(
            self.appdata / (dst or src), (self.service_dir / src).read_text()
        )

    def seed(self, src: str, dst: str | None = None) -> bool:
        """Write a starter file, then never touch it again.

        For config the service or a human goes on to own — Frigate's
        config.yaml, say, where later deploys must not clobber cameras added
        through the UI. Must run before `compose up`: if the bind mount source
        is missing at container start, Docker creates an empty directory and
        the service writes its own default, and that one-shot seed window is
        gone for good.
        """
        target = self.appdata / (dst or src)
        if target.exists():
            return False
        return self.write_if_changed(target, (self.service_dir / src).read_text())


def appdata_root() -> Path:
    """Where this process can see the appdata tree.

    deploy-agent mounts `${MNT_APPDATA}` at /appdata and sets APPDATA_DIR;
    run straight from the host there is no indirection and MNT_APPDATA is
    already the real path.
    """
    raw = os.environ.get("APPDATA_DIR") or os.environ.get("MNT_APPDATA")
    if not raw:
        raise HookError(
            "neither APPDATA_DIR nor MNT_APPDATA is set, so hooks cannot "
            "locate service data"
        )
    return Path(raw)


# One process is one deploy run, so caching keeps a service's module-level code
# to a single execution across both phases.
_MODULES: dict[Path, ModuleType | None] = {}


def load(service_dir: Path) -> ModuleType | None:
    """Import `<service_dir>/hooks.py`, or None if the service has no hooks."""
    if service_dir in _MODULES:
        return _MODULES[service_dir]

    path = service_dir / HOOKS_FILENAME
    if not path.is_file():
        _MODULES[service_dir] = None
        return None

    spec = importlib.util.spec_from_file_location(
        f"homelab_hooks.{service_dir.name}", path
    )
    if spec is None or spec.loader is None:
        raise HookError(f"{service_dir.name}: could not load {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise HookError(f"{service_dir.name}: {HOOKS_FILENAME} failed to import: {exc}")

    _MODULES[service_dir] = module
    return module


def fire(phase: str, service_dir: Path, *, proxy_subnet: str, run: Callable[..., str]) -> bool:
    """Run one phase for one service. True if the hook reported a change.

    A missing hooks.py, or a hooks.py without this phase, is the normal case
    and does nothing.
    """
    assert phase in PHASES, f"unknown hook phase: {phase}"

    module = load(service_dir)
    if module is None:
        return False
    func = getattr(module, phase, None)
    if func is None:
        return False

    ctx = Context(
        name=service_dir.name,
        service_dir=service_dir,
        appdata=appdata_root() / service_dir.name,
        proxy_subnet=proxy_subnet,
        run=run,
    )
    try:
        changed = func(ctx)
    except Exception as exc:
        raise HookError(f"{service_dir.name}: {phase} raised {type(exc).__name__}: {exc}")

    if changed:
        print(f"[deploy] {service_dir.name}: {phase} changed service data", flush=True)
    return bool(changed)
