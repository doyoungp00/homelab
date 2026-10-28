# What it's for

Authentik is an identity provider: one account per person, used to log in to every other service through OIDC, LDAP, or a login wall in front of Traefik.

[Check out the project](https://goauthentik.io)

# Why it's needed

1. Each service otherwise keeps its own accounts, so adding a person means signing them up everywhere, and removing one means finding every account they have.

2. Admin tools with no real login of their own (Glances, Scrutiny, the *arr apps) can sit behind one login with 2FA instead of being open to anyone on the network.

# Notes

1. It's served on both `auth.${DOMAIN_LOCAL}` and `auth.${DOMAIN_PUBLIC}`, since OIDC logins redirect the browser to it and some of its apps are public. The public hostname needs a DNS record, which ddclient's config (kept outside this repo) has to include.

2. The server and worker run as `568:568`, like the rest of the stack, instead of the image's default UID `1000`. `${MNT_APPDATA}/authentik/data` must be owned by `568` before the first deploy: Docker creates a missing bind mount source as `root`, and uploads (icons, branding) then fail. `hooks.py` hands `blueprints/` to `568` on every deploy, since files deploy-agent writes are otherwise root-only. Postgres runs as its own image's user and manages `postgres/` itself.

3. The image is pinned. Authentik's release notes list steps for each upgrade, so read them before bumping the tag. The Postgres major version is pinned too; a new major needs a dump and restore, not just a tag change.

4. The worker has no Docker socket, unlike upstream's compose. Outposts (e.g. LDAP) are added as services in this compose file instead of being created by Authentik.

5. Groups, providers, applications, and their access bindings are defined as blueprints in `blueprints/`. `hooks.py` copies them to `${MNT_APPDATA}/authentik/blueprints`, which the worker mounts at `/blueprints/homelab` and applies whenever a file changes (and hourly). Anything a blueprint sets is reverted on the next apply if edited in the UI, so change it here. Users, their passwords and MFA, and group membership aren't in blueprints and live only in the database under `${MNT_APPDATA}/authentik/postgres`.

6. Use `https://auth.${DOMAIN_PUBLIC}` everywhere: as the login wall's authentication URL and as every OIDC app's issuer. Authentik builds the issuer from the hostname it was reached on, so an app configured with the other hostname rejects its tokens. Containers and LAN clients must be able to reach the public hostname too, through hairpin NAT or an AdGuard rewrite.

7. The login wall is the `authentik` middleware, declared on Traefik's labels. A router opts in with `traefik.http.routers.<name>.middlewares=authentik@docker`. It's backed by a domain-level proxy provider (cookie domain `${DOMAIN_PUBLIC}`, which also covers `${DOMAIN_LOCAL}`) whose application only allows the `admins` group, so every service behind the wall shares that one rule. Homepage widgets for those services must use internal URLs, or they hit the login page.

8. Blueprint inputs are passed to the worker as plain environment variables (`DOMAIN_*`, `<APP>_OIDC_CLIENT_ID`, `<APP>_OIDC_CLIENT_SECRET`), each required in `compose.yaml` so a missing secret fails the deploy. Don't prefix them with `AUTHENTIK_`: authentik reads every such variable as its own setting. The app's side of an OIDC login (issuer, client ID and secret) usually lives in the app's own settings and has to be entered there to match.

9. Removing a blueprint from `blueprints/` stops it being applied, but leaves the objects it created. Delete those in the UI.
