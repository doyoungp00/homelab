"""Seed Frigate's config.yaml on a host that has never run it.

Seed, not sync: Frigate's web UI edits this same file, so cameras, detectors
and go2rtc settings added there must survive every later deploy. The repo only
gets to write it once.

That one chance is why this is pre_deploy. If ${MNT_APPDATA}/frigate/config is
missing when the container starts, Docker creates it as an empty directory,
Frigate writes its own default config, and the seed window is gone — later
deploys see a file and leave it alone, so the auth and tls blocks in
config/config.yaml never arrive. Nothing errors; they are just quietly absent.
"""

from __future__ import annotations


def pre_deploy(ctx):
    return ctx.seed("config/config.yaml", "config/config.yaml")
