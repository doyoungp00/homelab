"""Create gbrain's data directory and the wiki vault, owned by the apps user.

Docker creates a missing bind-mount source as root, and the appdata dataset's
inherited ACL leaves deploy-agent's directories root-only, so gbrain (568)
would fail at startup with EACCES on /data/.gbrain, and Hermes and Syncthing
(both 568) couldn't write the vault. Hermes' own /opt/data needs nothing here:
its image's init chowns it.

The vault starts as the skeleton in vault/ (schema, index, log, folders).
Seeded once, never overwritten: from then on Hermes and the person editing in
Obsidian own every file in it.
"""

from __future__ import annotations

import os

APPS_UID = 568

VAULT = "vault"
VAULT_FILES = ("AGENTS.md", "index.md", "log.md")
VAULT_DIRS = (
    "raw",
    "wiki",
    "wiki/sources",
    "wiki/entities",
    "wiki/concepts",
    "wiki/answers",
)


def pre_deploy(ctx):
    owned = [ctx.appdata / "gbrain", ctx.appdata / VAULT]
    for path in owned:
        path.mkdir(parents=True, exist_ok=True)

    for name in VAULT_FILES:
        ctx.seed(f"{VAULT}/{name}")
        owned.append(ctx.appdata / VAULT / name)
    for name in VAULT_DIRS:
        path = ctx.appdata / VAULT / name
        path.mkdir(parents=True, exist_ok=True)
        owned.append(path)

    # Only the skeleton: what's added later was created by 568 already.
    for path in owned:
        st = path.stat()
        if (st.st_uid, st.st_gid) != (APPS_UID, APPS_UID):
            os.chown(path, APPS_UID, APPS_UID)

    # Nothing a running container reads at startup changes here.
    return False
