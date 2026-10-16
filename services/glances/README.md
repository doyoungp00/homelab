# What it's for

Glances is a system monitor for CPU, memory, disks, network, sensors, and containers.

[Check out the project](https://github.com/nicolargo/glances)

# Why it's needed

It shows the host's resource usage in the browser and through the Homepage widget, without logging into the host.

# Known caveats

1. Glances runs with `network_mode: host` and `pid: host` to see the host's real network interfaces and processes. That means it can't join the `proxy` network, so Traefik reaches it at `${HOST_IP}:61208` instead of a container name.

2. The web UI has no password. Anyone who can reach it can see the host's processes and usage.

3. The host's root filesystem is mounted read-only at `/rootfs` to report disk usage.
