# What it's for

Dozzle is a real-time log viewer for Docker containers.

[Check out the project](https://dozzle.dev)

# Why it's needed

Logs for every container are available in the browser, without needing to SSH into the host and run `docker logs`. This is also where Deploy Agent's output is checked after triggering a deploy.

# Notes

1. Container actions (start, stop, restart) and shell access are enabled, so anyone signed in to Dozzle can control containers and open a shell in them. See note 3 for who that is.

2. Dozzle only reads logs from Docker. It doesn't store them, so logs are gone once Docker rotates them or a container is removed.

3. Login is through OIDC against the `dozzle` application in Authentik (`authentik/blueprints/dozzle.yaml`), only for the `admins` group, behind the login wall as well. Dozzle checks Authentik's token itself rather than trusting a forwarded username header, which anything on `proxy` could fake. Its permissions come from a `dozzle_roles` claim the blueprint sends to admins (`all`: shell, actions, downloads); a login without it is refused. `DOZZLE_OIDC_CLIENT_ID` and `DOZZLE_OIDC_CLIENT_SECRET` have to be set to the same values in both `dozzle/secret.sops.env` and `authentik/secret.sops.env`.

4. There's no password login in OIDC mode. If Authentik is down, Dozzle is unreachable; read logs with `docker logs` over SSH instead.
