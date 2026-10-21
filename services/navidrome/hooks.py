"""Install the nd-lyrics plugin into Navidrome's plugins folder.

Navidrome loads plugins from `<DataFolder>/plugins` at startup, and
`Plugins.AutoReload` is off by default, so the `.ndp` has to be on disk
before the container starts — hence pre_deploy. The truthy return earns
`--force-recreate`, which is what makes Navidrome restart and pick up a
newly installed or upgraded plugin; `write_if_changed` keeps a deploy that
changed nothing from restarting it for no reason.

The release is pinned rather than tracked at `latest`. This is a third-party
WebAssembly module running inside a publicly exposed service, so which build
is deployed should be a reviewable commit rather than whatever GitHub served
that morning, and a re-uploaded or tampered asset should fail the deploy
loudly instead of landing silently. Upgrading means bumping VERSION and
SHA256 together — see the README for how to get the new digest.

Editing this file is enough to redeploy navidrome on its own: deploy.py
diffs whole service directories, so a version bump needs no other change.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "v8.1.0"
SHA256 = "29dd571ba0d4bb756e62c0d5c594a2d7e7c9ccec2950f3b027bd64c73c605715"

# The filename is the plugin's identity: Navidrome names a plugin after its
# file without the extension, and that name is what ND_LYRICSPRIORITY in
# compose.yaml refers to. Renaming this breaks that reference.
PLUGIN = "nd-lyrics.ndp"

URL = (
    "https://github.com/J0R6IT0/navidrome-lyrics-plugin"
    f"/releases/download/{VERSION}/{PLUGIN}"
)

# `data` is what compose binds to /data, so this is /data/plugins in the
# container — the default Plugins.Folder for this DataFolder.
TARGET = Path("data") / "plugins" / PLUGIN


def pre_deploy(ctx) -> bool:
    target = ctx.appdata / TARGET

    try:
        with urllib.request.urlopen(URL, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError:
        # A 404 means VERSION names a tag or asset that isn't there, which is
        # a mistake in this file rather than an outage. Never paper over it —
        # the branch below would otherwise report success while doing nothing.
        raise
    except OSError as exc:
        # DNS, TLS, connection reset, timeout: GitHub or the uplink is down.
        # Only the first install genuinely needs the network, so don't let
        # that block a deploy that has nothing to do with the plugin.
        if target.is_file():
            print(
                f"[deploy] {ctx.name}: {PLUGIN} unreachable ({exc}); "
                "keeping the installed copy",
                flush=True,
            )
            return False
        raise

    digest = hashlib.sha256(payload).hexdigest()
    if digest != SHA256:
        raise ValueError(
            f"{PLUGIN} {VERSION} hashes to {digest}, expected {SHA256}. "
            "The release asset changed; verify it before bumping SHA256."
        )

    if not ctx.write_if_changed(target, payload):
        return False

    print(f"[deploy] {ctx.name}: installed {PLUGIN} {VERSION}", flush=True)
    return True
