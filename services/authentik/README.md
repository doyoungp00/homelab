# What it's for

Authentik is an identity provider: one account per person, used to log in to every other service through OIDC, LDAP, or a login wall in front of Traefik.

[Check out the project](https://goauthentik.io)

# Why it's needed

1. Each service otherwise keeps its own accounts, so adding a person means signing them up everywhere, and removing one means finding every account they have.

2. Admin tools with no real login of their own (Glances, Scrutiny, the *arr apps) can sit behind one login with 2FA instead of being open to anyone on the network.

# Notes

1. It's served on both `auth.${DOMAIN_LOCAL}` and `auth.${DOMAIN_PUBLIC}`, since OIDC logins redirect the browser to it and some of its apps are public. The public hostname needs a DNS record, which comes from the `DOMAINS` list in cloudflare-ddns's `compose.yaml`.

2. The server and worker run as `568:568`, like the rest of the stack, instead of the image's default UID `1000`. `${MNT_APPDATA}/authentik/data` must be owned by `568` before the first deploy: Docker creates a missing bind mount source as `root`, and uploads (icons, branding) then fail. `hooks.py` hands `blueprints/` to `568` on every deploy, since files deploy-agent writes are otherwise root-only. Postgres runs as its own image's user and manages `postgres/` itself.

3. The image is pinned. Authentik's release notes list steps for each upgrade, so read them before bumping the tag. The Postgres major version is pinned too; a new major needs a dump and restore, not just a tag change.

4. The worker has no Docker socket, unlike upstream's compose. Outposts (e.g. LDAP) are added as services in this compose file instead of being created by Authentik.

5. Groups, providers, applications, and their access bindings are defined as blueprints in `blueprints/`. `hooks.py` copies them to `${MNT_APPDATA}/authentik/blueprints`, which the worker mounts at `/blueprints/homelab` and applies whenever a file changes (and hourly). Anything a blueprint sets is reverted on the next apply if edited in the UI, so change it here. Users, their passwords and MFA, and group membership aren't in blueprints and live only in the database under `${MNT_APPDATA}/authentik/postgres`.

6. Use `https://auth.${DOMAIN_PUBLIC}` everywhere: as the login wall's authentication URL and as every OIDC app's issuer. Authentik builds the issuer from the hostname it was reached on, so an app configured with the other hostname rejects its tokens. Containers and LAN clients must be able to reach the public hostname too, through hairpin NAT or an AdGuard rewrite.

7. The login wall is the `authentik` middleware, declared on Traefik's labels. A router opts in with `traefik.http.routers.<name>.middlewares=authentik@docker`. It's backed by a domain-level proxy provider (cookie domain `${DOMAIN_PUBLIC}`, which also covers `${DOMAIN_LOCAL}`) whose application only allows the `admins` group, so every service behind the wall shares that one rule. Homepage widgets for those services must use internal URLs, or they hit the login page.

8. Blueprint inputs are passed to the worker as plain environment variables (`DOMAIN_*`, `<APP>_OIDC_CLIENT_ID`, `<APP>_OIDC_CLIENT_SECRET`), each required in `compose.yaml` so a missing secret fails the deploy. Don't prefix them with `AUTHENTIK_`: authentik reads every such variable as its own setting. The app's side of an OIDC login (issuer, client ID and secret) usually lives in the app's own settings and has to be entered there to match.

9. Removing a blueprint from `blueprints/` stops it being applied, but leaves the objects it created. Delete those in the UI.

10. `blueprints/ldap.yaml` serves an LDAP directory for apps that check passwords themselves (Jellyfin), through the `authentik-ldap` outpost container. LDAP can't ask for a second factor, so binds run a separate `ldap-authentication-flow` that accepts **app passwords only**: a person's main password works only on the web, behind MFA. Each person needs an app password, used as their password in those apps. The user settings (**Settings → Tokens and App passwords**) only offer an expiry date; for one that doesn't expire, create it as admin under **Directory → Tokens and App passwords**, with intent *App password*, the person as user, and Expiring off. To test one without Jellyfin, `ldapsearch` against `authentik-ldap:3389` with `-D cn=<username>,ou=users,dc=ldap,dc=goauthentik,dc=io`; `ldapwhoami` always ends in "Protocol error", since the outpost doesn't implement the who-am-I extension. Apps bind as the `ldap-search` service account to look users up; its app password is `LDAP_SEARCH_APP_PASSWORD`. Binds are cached, so a revoked app password can keep working until the outpost's cached session expires.

# Adding a person

1. Check the username is free everywhere it's matched by name. Nextcloud signs a login into any existing user with the same ID (`occ user:list`), and BookOrbit does the same with local linking on.

2. In Authentik, **Directory → Users → Create**: username, name, and an email that's theirs. Several apps link accounts by email, so emails are set by an admin only (**System → Settings**, "Allow users to change email" off). Then **Set password**, or send a recovery link if email is configured.

3. Add them to `family`, or to `admins` for the admin tools behind the login wall. Group bindings in `blueprints/` decide which apps let them in.

4. They log in at `auth.${DOMAIN_PUBLIC}` once and set up MFA.

Accounts are then created on first login in Immich, Karakeep, Dawarich, BookOrbit, Nextcloud, and Vaultwarden. A few things stay per app:

- **Vaultwarden:** they choose a master password on first login. Authentik never sees it.
- **wg-easy:** admins only, and not created automatically, since every wg-easy user is an administrator. An admin creates the wg-easy user, who then links Authentik from its account page.
- **Jellyfin and Seerr:** log in over LDAP with an app password (note 10). New users are created in Jellyfin on first login; give them an app password.
- **Frigate:** admins only, through the login wall.
- **Navidrome, Home Assistant, ntfy:** keep their own accounts. Create those by hand.

For someone who already has accounts from before Authentik, see each app's README: most link by email or username on first login, and some ask for the old password once.
