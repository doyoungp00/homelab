# What it's for

Frigate is a network video recorder (NVR) with real-time object detection for IP cameras.

[Check out the project](https://frigate.video)

# Why it's needed

1. Camera footage is recorded and stored locally, with no cloud subscription and no footage leaving the network. Cameras can stay disconnected from the internet entirely.

2. Object detection (people, cars, etc.) means recordings and alerts are based on actual events rather than any pixel change.

# Notes

1. `config/config.yaml` is only a starter config. `hooks.py` seeds it into appdata once, on a host that has never run Frigate. After that, Frigate's UI owns the live file, so changes to the repo copy are never applied. Edit the live config instead. This is a deliberate choice as camera setups are going to be different for every location.

2. `trusted_proxies` in the config must match the `proxy` network's subnet (`PROXY_SUBNET` in `scripts/deploy.py`). Otherwise Frigate sees every user as Traefik's IP and rate-limits them all as one client.

3. TLS is disabled in Frigate, since Traefik handles it. Enabling it breaks the route.

4. `frigate-stream` exposes port 5000, the unauthenticated UI/API, through Traefik so the Homepage camera card can load its stream over HTTPS. Anyone who can reach that hostname can view the cameras without logging in.

5. WebRTC (port 8555) is published directly on the host, not through Traefik.
