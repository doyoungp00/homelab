# What it's for

Dockhand is a web UI for managing Docker containers, images, and compose stacks.

[Check out the project](https://github.com/Finsys/dockhand)

# Why it's needed

It gives an overview of every container on the host in one place, and shows when newer images are available for services that use a plain `image:` tag.

# Notes

1. Dockhand has read-write access to the Docker socket, which is effectively root on the host. It sits behind the Authentik login wall, and its own login uses OIDC against the `dockhand` application in Authentik (`authentik/blueprints/dockhand.yaml`), which only the `admins` group can use. The OIDC settings on Dockhand's side live in its database, not this repo; see "Setting up OIDC" below. Keep the local admin account as a way back in if Authentik is down.

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

4. Keep the local admin account and password login (don't set `DISABLE_LOCAL_LOGIN`) as a way back in if Authentik is down.
