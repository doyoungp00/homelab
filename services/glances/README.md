# What it's for

Glances is a system monitor for CPU, memory, disks, network, sensors, and containers.

[Check out the project](https://github.com/nicolargo/glances)

# Why it's needed

It shows the host's resource usage in the browser and through the Homepage widget, without logging into the host.

# Notes

1. Glances runs with `network_mode: host` and `pid: host` to see the host's real network interfaces and processes. That means it can't join the `proxy` network, so Traefik, Homepage, and Gatus reach it at `172.16.25.1:61208`, the `proxy` network's gateway, instead of a container name.

2. The web UI, API, and MCP endpoint have no password. They listen only on `172.16.25.1` (`-B`), so only containers on `proxy` can reach them directly. People go through `glances.${DOMAIN_LOCAL}`, behind the Authentik login wall. Every container on `proxy` can still read them without logging in.

3. `172.16.25.1` is the gateway Docker assigns to the `proxy` network created by `scripts/deploy.py` on `PROXY_SUBNET`. If that subnet ever changes, this address changes with it, in `compose.yaml` and Homepage's `services.yaml`.

4. The host's root filesystem is mounted read-only at `/rootfs` to report disk usage.
