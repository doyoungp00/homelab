# What it's for

Dockhand is a web UI for managing Docker containers, images, and compose stacks.

[Check out the project](https://github.com/Finsys/dockhand)

# Why it's needed

It gives an overview of every container on the host in one place, and shows when newer images are available for services that use a plain `image:` tag.

# Notes

1. Dockhand has read-write access to the Docker socket, which is effectively root on the host. It sits behind the Authentik login wall, and its own login uses OIDC against the `dockhand` application in Authentik (`authentik/blueprints/dockhand.yaml`), which only the `admins` group can use. The OIDC settings on Dockhand's side live in its database, not this repo; see "Setting up OIDC" below. Password login is off (`DISABLE_LOCAL_LOGIN=true`), so OIDC is the only way in. If Authentik is down, remove that line and redeploy, or run `docker exec -it dockhand /app/scripts/emergency/sqlite/disable-auth.sh`, which turns Dockhand's authentication off until it's re-enabled in its settings.

2. Deployments are owned by Deploy Agent and this repo. Changes made to a stack through Dockhand will be reverted the next time that service is deployed. Make permanent changes in the repo instead.

# Setting up OIDC

Authentik's side (provider, redirect URI, `admins`-only access) is created by `authentik/blueprints/dockhand.yaml`. Dockhand's side is stored in its database and has to be entered by hand once, on a fresh install or after its data is lost.

1. Add `DOCKHAND_OIDC_CLIENT_ID` and `DOCKHAND_OIDC_CLIENT_SECRET` to `authentik/secret.sops.env` (e.g. `openssl rand -hex 20` and `openssl rand -hex 48`), deploy, and check that **Customization → Blueprints** in Authentik shows `homelab - dockhand` as successful.

2. In Dockhand, open **Settings → Authentication → SSO / OIDC → Add Provider**. On the **General** tab, set:

   | Field                                 | Value                                                                                   |
   | ------------------------------------- | --------------------------------------------------------------------------------------- |
   | Name                                  | `Authentik` (the login button's label)                                                  |
   | Issuer URL                            | `https://auth.${DOMAIN_PUBLIC}/application/o/dockhand/`. Keep the trailing slash.       |
   | Enable this OIDC provider             | On                                                                                      |
   | Client ID                             | `DOCKHAND_OIDC_CLIENT_ID`                                                               |
   | Client secret                         | `DOCKHAND_OIDC_CLIENT_SECRET`                                                           |
   | Redirect URI                          | `https://dockhand.${DOMAIN_LOCAL}/api/auth/oidc/callback`, the URI the blueprint allows |
   | Scopes                                | `openid profile email`                                                                  |
   | Username / Email / Display name claim | `preferred_username` / `email` / `name`                                                 |

   Leave the **Role mapping** tab alone; it's a paid feature, and access is already limited to `admins` in Authentik.

3. Test the OIDC login in a private window. If the account it signs in to isn't an admin, grant it admin from the local admin account.

4. Once the OIDC login works, `DISABLE_LOCAL_LOGIN=true` in `compose.yaml` turns password login off (see note 1 for getting back in).

# Homepage widget

Homepage calls `http://dockhand:3000` directly, so the Authentik wall doesn't apply, but Dockhand's own login does. The widget can't use OIDC, and its username/password login is rejected while `DISABLE_LOCAL_LOGIN=true`, so it uses an API token instead. Tokens are stored in Dockhand's database, so this has to be redone if its data is lost.

1. In Dockhand, sign in and open **Profile → API tokens**. Create a token named `homepage` with no expiry, and copy it (`dh_…`, shown once).

2. Add it as `DOCKHAND_HOMEPAGE_KEY` to `dockhand/secret.sops.env` and deploy.

The token acts as the user who created it, so it has full admin rights. Only Homepage's server side sees it; it isn't sent to the browser.
