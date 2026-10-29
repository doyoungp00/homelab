# What it's for

Karakeep is a bookmarking app for links, notes, and images, with full-text search and page archiving.

[Check out the project](https://karakeep.app)

# Why it's needed

1. Saved pages are archived locally (screenshots, PDF, full page, and video), so they stay readable even if the original page changes or goes offline.

2. Bookmarks are searchable through Meilisearch, and can be tagged automatically by AI if `OPENAI_API_KEY` is set.

# Notes

1. Full page archives, PDFs, and video downloads are all enabled, which can use a lot of disk space over time.

2. Meilisearch is pinned to a specific version. Upgrading it across versions may require a dump and re-import of the index.

3. The headless Chrome container (port 9222) has no authentication and is reachable by any container on the `proxy` network.

4. Login is through OIDC against the `karakeep` application in Authentik (`authentik/blueprints/karakeep.yaml`), open to the `admins` and `family` groups. Unlike most apps, both sides are in this repo: Karakeep reads its OIDC settings from `OAUTH_*` variables. `KARAKEEP_OIDC_CLIENT_ID` and `KARAKEEP_OIDC_CLIENT_SECRET` have to be set to the same values in both `karakeep/secret.sops.env` and `authentik/secret.sops.env`.

5. `OAUTH_ALLOW_DANGEROUS_EMAIL_ACCOUNT_LINKING` links a first OAuth login to the existing account with the same email. Without it, Authentik's `email_verified: false` makes Karakeep create a new, empty account instead, so a person's Authentik email must match their Karakeep one. The callback Authentik allows is `https://karakeep.${DOMAIN_LOCAL}/api/auth/callback/custom`, which Karakeep builds from `NEXTAUTH_URL`. Both are derived from `DOMAIN_LOCAL` in `compose.yaml`, not kept in sops, so they can't drift apart; if the hostname changes, change both.

6. Karakeep isn't behind the login wall: the browser extension and mobile apps call its API directly with API keys. Password login is off (`DISABLE_PASSWORD_AUTH=true`): OAuth is the only way in, and new people get an account on their first Authentik login. If Authentik is down, remove that line and redeploy.
