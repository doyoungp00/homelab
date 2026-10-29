# What it's for

Frigate is a network video recorder (NVR) with real-time object detection for IP cameras.

[Check out the project](https://frigate.video)

# Why it's needed

1. Camera footage is recorded and stored locally, with no cloud subscription and no footage leaving the network. Cameras can stay disconnected from the internet entirely.

2. Object detection (people, cars, etc.) means recordings and alerts are based on actual events rather than any pixel change.

# Notes

1. `config/config.yaml` is only a starter config. `hooks.py` seeds it into appdata once, on a host that has never run Frigate. After that, Frigate's UI owns the live file, so changes to the repo copy are never applied. Edit the live config instead. This is a deliberate choice as camera setups are going to be different for every location.

2. Logins come from Authentik: Frigate's own login is off (`auth.enabled: false`), and it reads the user and groups from Authentik's headers, mapping `admins` to Frigate's `admin` role and anyone else to `viewer`. It only trusts those headers alongside `X-Proxy-Secret`, which Traefik's `frigate-proxy-secret` middleware adds and `proxy.auth_secret` checks, both from `FRIGATE_PROXY_SECRET`. Without that, anything on the `proxy` network could send the headers itself. The route is behind the login wall, so only `admins` reach it.

3. TLS is disabled in Frigate, since Traefik handles it. Enabling it breaks the route.

4. `frigate-stream` exposes port 5000, the unauthenticated UI/API, through Traefik so the Homepage camera card can load its stream over HTTPS. It's behind the login wall; the card loads in a browser that already has the dashboard's Authentik session. Homepage's widget and Gatus use port 5000 directly over the `proxy` network, as Home Assistant's integration does, so anything on that network can still read it.

5. WebRTC (port 8555) is published directly on the host, not through Traefik.

# Setting up Authentik login

`config/config.yaml` has these settings for a fresh host, but on an existing one Frigate owns the live file, so they're entered once by hand. Deploy the compose change first: with Frigate's login still on, the extra header is harmless, while the other order locks everyone out until Traefik sends the secret.

1. Add `FRIGATE_PROXY_SECRET` to `frigate/secret.sops.env` (`python3 -c 'import secrets; print(secrets.token_hex(64))'`) and deploy.

2. Keep a Frigate admin's password in Vaultwarden. Turning the login back on (`auth.enabled: true`) is the way in if Authentik is down.

3. In `${MNT_APPDATA}/frigate/config/config.yaml` (or Frigate's config editor), replace the `auth` block with the `auth` and `proxy` blocks from `config/config.yaml`, and restart Frigate. `{FRIGATE_PROXY_SECRET}` stays as written; Frigate fills it in from the environment.

4. Open Frigate: it should go straight in, with your Authentik username and the admin role in the user menu.
