# What it's for

Firefox running in a container, used from any browser through a web GUI. All of its traffic goes through its own Gluetun VPN tunnel, so it works as a VPN-tunneled browser without a VPN client on the device using it.

[Check out the project](https://github.com/linuxserver/docker-firefox)

# Why it's needed

Some sites are blocked or behave differently from the home IP. This browses them from the VPN's IP without routing the whole device, or the rest of the homelab, through the VPN.

# Notes

1. Firefox uses `network_mode: service:firefox-gluetun`, so it has no network identity of its own. Its Traefik and Gatus labels live on `firefox-gluetun`, and other containers reach it at `firefox-gluetun:3000`. Its Homepage labels stay on `firefox` itself: Homepage reads labels through the Docker API without connecting to the container, so the card shows Firefox's own status. Gluetun's firewall blocks any traffic that would leave outside the tunnel, so if the VPN drops, Firefox loses its connection instead of falling back to the home IP.

2. When `firefox-gluetun` is recreated it gets a new container ID and Firefox is left with no network. `hooks.py` recreates Firefox after each deploy when that happens (see `scripts/gluetun.py`). A `firefox-gluetun` that restarts in place keeps its ID, so the hook doesn't fire; run `docker restart firefox` by hand.

3. This is a separate tunnel from arr-stack's `gluetun` and needs its own WireGuard key: generate a second WireGuard config at the VPN provider and set `GLUETUN_WIREGUARD_PRIVATE_KEY` in this service's `secret.sops.env`. Two tunnels connecting with one key can knock each other off. No port forwarding is set up, since a browser doesn't need inbound connections.

4. The GUI has no login of its own and includes a terminal with passwordless sudo, so anyone who reaches it gets root in the container. It is only reachable through Traefik behind the Authentik login wall; don't publish its ports.

5. `/config` is Firefox's home directory, so the profile (bookmarks, logins, cookies) persists across container updates.
