"""Rejoin the containers in gluetun's network namespace after gluetun is replaced.

See scripts/gluetun.py for why, and the README for what it can't catch.
"""

from __future__ import annotations

from scripts.gluetun import rejoin


def post_deploy(ctx) -> bool:
    return rejoin(ctx, "gluetun", ("prowlarr", "qbittorrent", "suwayomi-server"))
