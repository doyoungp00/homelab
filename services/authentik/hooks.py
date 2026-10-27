"""Mirror services/authentik/blueprints/ into appdata, where the worker reads it.

The worker mounts ${MNT_APPDATA}/authentik/blueprints read-only at
/blueprints/homelab. A relative `./blueprints` mount wouldn't do: deploy-agent
runs compose against its own /repo, and the Docker daemon resolves bind mount
sources on the host, where no such path exists.

The repo owns the directory outright. A blueprint deleted from the repo is
deleted here too, so authentik stops applying it (the objects it created stay,
and are removed in the UI).
"""

from __future__ import annotations

BLUEPRINTS = "blueprints"


def pre_deploy(ctx):
    src_dir = ctx.service_dir / BLUEPRINTS
    dst_dir = ctx.appdata / BLUEPRINTS
    wanted = {p.name for p in src_dir.glob("*.yaml")}

    for name in sorted(wanted):
        ctx.sync(f"{BLUEPRINTS}/{name}")
    if dst_dir.is_dir():
        for stale in dst_dir.glob("*.yaml"):
            if stale.name not in wanted:
                stale.unlink()

    # Never asks for a recreate. The worker watches the directory and applies
    # changed blueprints on its own, so restarting the stack (database
    # included) would only take every login down for nothing.
    return False
