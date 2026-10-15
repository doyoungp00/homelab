"""Keep appdata's acquis.yaml in step with the one in git.

compose.yaml bind-mounts ${MNT_APPDATA}/crowdsec/acquis.yaml over
/etc/crowdsec/acquis.d/homelab.yaml. Syncing it from the repo rather than
baking it into an image keeps the file version-controlled while leaving the
service on a plain `image:` — so Dockhand can still see updates for it and
`compose pull` still applies them.

Entirely repo-owned: nothing but this file should ever write it, so drift gets
overwritten rather than merged.
"""

from __future__ import annotations


def pre_deploy(ctx):
    return ctx.sync("acquis.yaml")
