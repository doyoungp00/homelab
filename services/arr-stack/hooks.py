"""Rejoin the containers in gluetun's network namespace after gluetun is replaced.

Prowlarr, qBittorrent, and Suwayomi-Server run with `network_mode:
service:gluetun`, which compose resolves when it *creates* them, writing the
literal `container:<id>` of whichever gluetun container existed at that moment
into their HostConfig. Recreating gluetun (an image update, etc) gives
it a new id, and the three are left pointing at one that no longer exists:
still running, still healthy by their own healthchecks, with no network.

`compose up` cannot notice. It decides what to recreate by hashing the resolved
compose config, and that config still reads `service:gluetun`; only the id
behind it moved. Adding `restart: true` to their `depends_on` wouldn't fix it
either, for two reasons: it fires only when compose itself updates the
dependency, and a *restart* re-enters the same stale HostConfig. The repair has
to be a recreate.

So compare the resolved id directly, after the deploy, and recreate only what
drifted. Every deploy that leaves gluetun alone is a no-op.

This is deploy-time only. A gluetun that restarts in place (crash, `docker restart`)
keeps its id, so nothing here fires even though the
dependents have lost their namespace just the same. See the README.
"""

from __future__ import annotations

GLUETUN = "gluetun"

# Every service in compose.yaml with `network_mode: service:gluetun`. Listed
# rather than parsed out of the YAML as they rarely change, and a stale entry
# here is harmless (a container that doesn't exist is skipped).
NAMESPACE_SHARERS = ("prowlarr", "qbittorrent", "suwayomi-server")


def container_id(ctx, name: str) -> str:
    """Full id of the container called `name`, or "" if there isn't one."""
    return ctx.run("docker", "ps", "-aq", "--no-trunc", "-f", f"name=^{name}$")


def current_namespaces(gluetun_id: str) -> set[str]:
    """The HostConfig.NetworkMode values that mean "attached to this gluetun".

    The id form is what compose writes today, and the only one that can go
    stale. The name form is accepted because if a future compose resolves to
    `container:gluetun` instead, Docker re-resolves it on every start and there
    is nothing to repair. This hook should sit quiet rather than recreate
    three containers on every single deploy.
    """
    return {
        f"container:{gluetun_id}",
        f"container:{gluetun_id[:12]}",
        f"container:{GLUETUN}",
    }


def post_deploy(ctx) -> bool:
    gluetun_id = container_id(ctx, GLUETUN)
    if not gluetun_id:
        # No gluetun to rejoin. `compose up` has already failed loudly if that
        # wasn't deliberate, so don't pile a second error on top of it.
        return False

    current = current_namespaces(gluetun_id)
    stale = [
        name
        for name in NAMESPACE_SHARERS
        if container_id(ctx, name)
        and ctx.run("docker", "inspect", "-f", "{{.HostConfig.NetworkMode}}", name)
        not in current
    ]
    if not stale:
        return False

    print(f"[deploy] {ctx.name}: rejoining {', '.join(stale)} to {GLUETUN}", flush=True)
    # --no-deps matters: naming services on `up` otherwise brings their
    # depends_on along, and force-recreating gluetun would hand it a third id,
    # invalidating the namespaces this call just repaired.
    ctx.run(
        "docker",
        "compose",
        "--project-directory",
        str(ctx.service_dir),
        "up",
        "-d",
        "--force-recreate",
        "--no-deps",
        *stale,
    )
    return True
