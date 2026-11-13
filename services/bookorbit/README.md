# What it's for

BookOrbit is a self-hosted library for ebooks and audiobooks, with reading progress, metadata management, and optional text-to-speech.

[Check out the project](https://github.com/bookorbit/bookorbit)

# Why it's needed

Books on the NAS can be browsed, read, and downloaded from any device through the browser, without installing anything.

# Notes

1. `SETUP_BOOTSTRAP_TOKEN` is asked for when creating the first admin account. It's only needed once.

2. `PATH_BOOKS` must be readable and writable by `PUID:PGID`. BookOrbit only fixes ownership of its own `/data` directory, not the books folder, and needs write access for uploads and metadata write-back.

3. The app and PostgreSQL data must be on a local filesystem, not a network mount.

4. The Kokoro text-to-speech container is opt-in and doesn't start by default. Run with `--profile tts` to enable it.

5. Login is through OIDC against the `bookorbit` application in Authentik (`authentik/blueprints/bookorbit.yaml`), open to the `admins` and `family` groups. BookOrbit's side of it is in its own settings, not this repo; see "Setting up OIDC" below. `OIDC_ALLOW_LOCAL_ISSUERS` is on so BookOrbit accepts Authentik when its hostname resolves to a LAN address.

6. BookOrbit matches OIDC logins to existing accounts by username, and only with "local linking" on. It's left off, so existing accounts are linked from their own account settings while logged in. An unlinked existing user who signs in with OIDC gets an error, not a duplicate account, because their username is already taken.

7. Outside the LAN, only the KOReader plugin's API is reachable, at `bookorbit.${DOMAIN_PUBLIC}`: `/api/v1/koreader/users/auth`, `/api/v1/koreader/syncs/*` and `/api/v1/koreader/plugin/*`, rate limited per IP. Those routes take KOReader sync credentials (Settings → KOReader), not the web login, and can't go behind Authentik because KOReader can't follow a browser login. The web UI stays LAN-only. In the plugin, set the server address to `https://bookorbit.${DOMAIN_PUBLIC}`, which works both at home and away. See "Risks of the public KOReader route" below.

# Risks of the public KOReader route

What's left open by exposing the plugin's API (note 7), as assessed against BookOrbit's source in November 2026. Recheck when the plugin adds endpoints: a call outside the matched paths 404s from outside the LAN.

1. **The plugin probably doesn't verify TLS certificates.** Its proxy code sets `verify = "none"`, and KOReader's HTTPS stack generally doesn't verify either. On untrusted Wi-Fi, a man in the middle could read the traffic and capture the sync key. The key is an unsalted MD5 of the password, which the server accepts as the credential itself.

2. **What a stolen sync credential can do.** Browse and download every book the account can see, change reading status, ratings and progress, and upload or delete highlights. It can't log in to the web UI, reach admin routes, or delete files.

3. **Brute force is limited only by the password.** BookOrbit doesn't throttle these routes. The Traefik rate limit (5/s per IP, burst 60) stops one IP from tying up the CPU with bcrypt checks, but barely slows password guessing, and it's not known whether CrowdSec's default scenarios flag repeated 401s. Use a long random password for the sync credentials.

4. **Bugs in the exposed code.** A flaw in the KOReader routes, or in the code that runs before them, is reachable from the internet. Container hardening limits the damage, but `/books` and `/downloads` are mounted read-write, and the container is on the shared `proxy` network, so it can reach other services directly, bypassing Traefik and Authentik.

5. **Plugin self-update.** The plugin downloads updates from `/koreader/plugin/package`. Without certificate checks (item 1), someone in the middle could push code to the e-reader.

6. **Minor.** The hostname is visible in public certificate-transparency logs. The path allowlist relies on Traefik and Fastify not resolving encoded `../` tricks out of the matched prefixes.

# Setting up OIDC

Authentik's side (provider, redirect URIs, who may log in) is created by `authentik/blueprints/bookorbit.yaml`. BookOrbit's side is stored in its database and has to be entered by hand once, on a fresh install or after its data is lost.

1. Add `BOOKORBIT_OIDC_CLIENT_ID` and `BOOKORBIT_OIDC_CLIENT_SECRET` to `authentik/secret.sops.env` (e.g. `openssl rand -hex 20` and `openssl rand -hex 48`), deploy, and check that **Customization → Blueprints** in Authentik shows `homelab - bookorbit` as successful.

2. In BookOrbit, add an OIDC provider under its authentication settings:

   | Field               | Value                                                                      |
   | ------------------- | -------------------------------------------------------------------------- |
   | Slug                | `authentik`                                                                |
   | Display name        | `Authentik`                                                                |
   | Enabled             | On                                                                         |
   | Issuer URI          | `https://auth.${DOMAIN_PUBLIC}/application/o/bookorbit/`                   |
   | Client ID           | `BOOKORBIT_OIDC_CLIENT_ID`                                                 |
   | Client secret       | `BOOKORBIT_OIDC_CLIENT_SECRET`                                             |
   | Scopes              | `openid email profile`                                                     |
   | Claim mapping       | Username `preferred_username`, name `name`, email `email`, groups `groups` |
   | Auto-provision      | On, so new people get an account on first login                            |
   | Allow local linking | Off. Existing accounts are linked by hand (step 3).                        |
   | Default permissions | Whatever a new family member should have                                   |

3. Each existing user logs in with their password, opens their account settings, and links Authentik there.

4. Test the Authentik button in a private window. Keep password login as a way back in if Authentik is down.
