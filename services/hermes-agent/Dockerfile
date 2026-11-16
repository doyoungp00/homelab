# gbrain has no published image. This installs a pinned release of its CLI,
# which the compose file runs as `gbrain serve --http`.
FROM docker.io/oven/bun:1

# Bump to upgrade. The stable channel's current release:
# https://github.com/garrytan/gbrain/blob/stable/VERSION
ARG GBRAIN_VERSION=v0.60.728.0

# git: bun installs gbrain straight from GitHub.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installed outside any home directory, so the runtime user (568, set in
# compose) can run it without owning it. GBRAIN_NO_AUTOPILOT_INSTALL: the
# container is the service; nothing should try to install a daemon.
ENV BUN_INSTALL=/opt/bun \
    PATH=/opt/bun/bin:$PATH \
    GBRAIN_NO_AUTOPILOT_INSTALL=1
RUN bun install -g "github:garrytan/gbrain#${GBRAIN_VERSION}" \
    && gbrain --version

# Config, tokens and caches live under GBRAIN_HOME (mounted from appdata).
# The brain itself is in Postgres.
ENV HOME=/data \
    GBRAIN_HOME=/data
WORKDIR /data

ENTRYPOINT ["gbrain"]
# starter: the 29 everyday tools instead of all 127, which would crowd the
# model's context; anything left out stays reachable through request_tools.
CMD ["serve", "--http", "--port", "3131", "--bind", "0.0.0.0", "--surface", "starter"]
