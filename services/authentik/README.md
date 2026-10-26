# What it's for

Authentik is an identity provider: one account per person, used to log in to every other service through OIDC, LDAP, or a login wall in front of Traefik.

[Check out the project](https://goauthentik.io)

# Why it's needed

1. Each service otherwise keeps its own accounts, so adding a person means signing them up everywhere, and removing one means finding every account they have.

2. Admin tools with no real login of their own (Glances, Scrutiny, the *arr apps) can sit behind one login with 2FA instead of being open to anyone on the network.

# Notes

1. It's served on both `auth.${DOMAIN_LOCAL}` and `auth.${DOMAIN_PUBLIC}`, since OIDC logins redirect the browser to it and some of its apps are public. The public hostname needs a DNS record, which ddclient's config (kept outside this repo) has to include.

2. `${MNT_APPDATA}/authentik/data` must be writable by UID `1000`, the user the image runs as. Docker creates a missing bind mount source as `root`, and uploads (icons, branding) then fail.

3. The image is pinned. Authentik's release notes list steps for each upgrade, so read them before bumping the tag. The Postgres major version is pinned too; a new major needs a dump and restore, not just a tag change.

4. The worker has no Docker socket, unlike upstream's compose. Outposts (e.g. LDAP) are added as services in this compose file instead of being created by Authentik.

5. Users, groups, and application settings live in the database under `${MNT_APPDATA}/authentik/postgres`, not in this repo.
