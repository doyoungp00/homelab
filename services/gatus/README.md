# What it's for

Gatus is a health and uptime dashboard that checks each service on an interval.

[Check out the project](https://github.com/TwiN/gatus)

This stack also runs a custom **gatus-generator** container. Gatus only reads a static `config.yaml`, so the generator builds that file from `gatus.*` labels on running containers every 30 seconds. See the docstring in `generator.py` for the full label format.

# Why it's needed

1. It shows at a glance which services are down or slow, with uptime history, and feeds the Gatus widget on Homepage.

2. With the generator, adding monitoring for a service is just a few labels in its `compose.yaml`, the same way Traefik and Homepage are configured.

# Notes

1. `config.yaml` is regenerated constantly. Manual edits are overwritten within 30 seconds.

2. The generator only lists running containers. A stopped container disappears from Gatus instead of showing as down.

3. Checks go directly to containers over the `proxy` network, not through Traefik. A broken route or certificate won't be caught.

4. Docker labels can't repeat a key. A container that serves several services (e.g. via `network_mode: service:gluetun`) needs indexed labels like `gatus[1].url`.

5. `gatus.alert=true` on a container sends an ntfy notification when that endpoint fails three checks in a row, and again when it recovers. It's opt-in per endpoint: monitoring everything is useful, but being paged for everything isn't. The `alerting` block only appears in `config.yaml` once at least one container carries the label.

6. Alerting needs `NTFY_TOKEN` in gatus's `secret.sops.env` — a token for the `gatus` account on ntfy, which has write-only access to the `alerts` topic. The generator writes the literal string `${NTFY_TOKEN}` into `config.yaml` and Gatus expands it at load, so the token never lands in the file. Without the variable set, Gatus starts but every alert gets a 401 from ntfy.

7. The dashboard is behind the Authentik login wall, not Gatus's built-in OIDC. OIDC would also lock the status API that Homepage's Gatus widget reads, and Gatus has no accounts to sign in to anyway. Homepage's widget uses `gatus:8080` directly, and its embedded `gatus-overview` frame passes the wall on the same Authentik session as the dashboard.
