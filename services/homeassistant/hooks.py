"""Point Home Assistant at Traefik's X-Forwarded-For.

Without this every request looks like it came from Traefik's container IP:
the ip_ban and login-attempt machinery then counts the whole household as one
client, and one person fat-fingering a password locks out everybody.

config/.storage/http is machine-owned JSON that HA rewrites itself, so on a
host that has already run HA this merges two keys and leaves the rest alone.
On a host that hasn't, there is nothing to merge into — HA only writes the file
partway through its first boot, by which point it has already decided how to
read client IPs. Waiting for the second deploy would leave the first one
misconfigured, so the file is seeded in full instead.

Setting it in configuration.yaml is no longer an option: HA 2026.9 migrated the
http: block into this file and now ignores the YAML, and it hard-fails in
2027.2.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

STORAGE = "config/.storage/http"
CONTAINER = "homeassistant"

# Schema of the storage key as HA 2026.9 writes it. version/minor_version are
# what let HA migrate this forward if the schema moves, so they have to be
# honest about which schema the rest of this dict is.
STORAGE_VERSION = 2
STORAGE_MINOR_VERSION = 2

# Only consulted when the file is absent, so these are first-boot defaults, not
# settings this hook enforces — edit them in HA's UI afterwards and they stick.
# server_port is pinned deliberately: HA 2026.8 made port 80 the default for
# fresh installs, which would silently miss Traefik's 8123 on a rebuilt host.
SEED_DEFAULTS = {
    "server_port": 8123,
    "cors_allowed_origins": ["https://cast.home-assistant.io"],
    "login_attempts_threshold": -1,
    "ip_ban_enabled": True,
    "ssl_profile": "modern",
    "use_x_frame_options": True,
    "error": None,
    "error_message": None,
}


def desired_proxy_settings(ctx):
    return {"use_x_forwarded_for": True, "trusted_proxies": [ctx.proxy_subnet]}


def seed(ctx, path):
    """Write the storage key HA has not written yet.

    yaml_migration_done is true because there is no YAML to migrate from; left
    false, HA's migration pass would run on first boot and overwrite these
    values with what it found (or didn't) in configuration.yaml.
    """
    data = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_MINOR_VERSION,
        "key": "http",
        "data": {
            "stable": SEED_DEFAULTS
            | {"created_at": datetime.now(timezone.utc).isoformat()}
            | desired_proxy_settings(ctx),
            "pending": None,
            "yaml_migration_done": True,
        },
    }
    return ctx.write_if_changed(path, json.dumps(data, indent=2) + "\n")


def pre_deploy(ctx):
    path = ctx.appdata / STORAGE
    if not path.is_file():
        # HA has never booted here. Nothing is running to stop, and the write
        # lands before the container starts, so it reads this on first boot.
        return seed(ctx, path)

    data = json.loads(path.read_text())
    stable = data.get("data", {}).get("stable")
    if stable is None:
        return False

    desired = desired_proxy_settings(ctx)
    if all(stable.get(key) == value for key, value in desired.items()):
        return False
    stable.update(desired)

    # HA flushes .storage on clean shutdown, so writing this while it runs just
    # hands it back to the stop that compose is about to perform. Stop first;
    # the --force-recreate our True return triggers brings it back up.
    if ctx.run("docker", "ps", "-q", "-f", f"name=^{CONTAINER}$"):
        ctx.run("docker", "stop", CONTAINER)

    return ctx.write_if_changed(path, json.dumps(data, indent=2) + "\n")
