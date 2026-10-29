# What it's for

Immich is a self-hosted photo and video library, similar to Google Photos.

[Check out the project](https://immich.app)

# Why it's needed

1. Photos and videos are backed up automatically from phones and stored on the NAS, without depending on a cloud storage plan.

2. Machine learning features like face recognition and smart search run locally. The ML container uses OpenVINO with the host's Intel GPU (`/dev/dri`).

# Notes

1. Immich releases often include breaking changes. Read the release notes before updating, especially across major versions.

2. The Postgres and Valkey images are pinned by digest, as in Immich's official compose file. Update them only when Immich's release notes say to.

3. The `-openvino` ML image only works on Intel hardware. Use a different tag (or none) on other hardware.

4. Login is through OIDC against the `immich` application in Authentik (`authentik/blueprints/immich.yaml`), open to the `admins` and `family` groups. Immich's side of it is in its own admin settings, not this repo; see "Setting up OIDC" below. A first OAuth login links to the existing account with the same email, so a person's Authentik email must match their Immich one, or they get a new, empty account. Immich isn't behind the login wall: the mobile apps and shared links need to reach it directly.

# Setting up OIDC

Authentik's side (provider, redirect URIs, who may log in) is created by `authentik/blueprints/immich.yaml`. Immich's side is stored in its database and has to be entered by hand once, on a fresh install or after its database is lost.

1. Add `IMMICH_OIDC_CLIENT_ID` and `IMMICH_OIDC_CLIENT_SECRET` to `authentik/secret.sops.env` (e.g. `openssl rand -hex 20` and `openssl rand -hex 48`), deploy, and check that **Customization → Blueprints** in Authentik shows `homelab - immich` as successful.

2. Before anyone logs in, make sure each Immich user's email (**Administration → Users**) matches their Authentik email exactly.

3. In Immich, open **Administration → Settings → Authentication Settings → OAuth** and set:

   | Field                        | Value                                                                        |
   | ---------------------------- | ---------------------------------------------------------------------------- |
   | Enable                       | On                                                                           |
   | Issuer URL                   | `https://auth.${DOMAIN_PUBLIC}/application/o/immich/`                        |
   | Client ID                    | `IMMICH_OIDC_CLIENT_ID`                                                      |
   | Client Secret                | `IMMICH_OIDC_CLIENT_SECRET`                                                  |
   | Scope                        | `openid email profile`                                                       |
   | Signing Algorithm            | `RS256`                                                                      |
   | Storage Label Claim          | `preferred_username`                                                         |
   | Role Claim                   | Leave as default. Authentik doesn't send it, so roles stay as set in Immich. |
   | Button Text                  | Optional, e.g. `Login with Authentik`                                        |
   | Auto Register                | On, so new people get an account on first login                              |
   | Auto Launch                  | Off until password login is disabled                                         |
   | Mobile Redirect URI Override | Off. Authentik accepts `app.immich:///oauth-callback` as is.                 |

   Leave **Password Login** on until everyone has linked, then turn it off. If Authentik is down after that, `docker exec immich_server immich-admin enable-password-login` turns it back on.

4. Test in a private window with **Login with OAuth**. An existing user should land in their own library. An empty library means the email didn't match and a new account was created with the Authentik email instead. As an admin, delete that new account under **Administration → Users**, change the original account's email to the Authentik one, and log in again; it then links to the original.

5. On the mobile app, log out, enter the server URL, and use the OAuth button.

If login fails with "Failed to finish OAuth", set **Administration → Settings → Logging** to debug and check `docker logs immich_server`. The error from Authentik is in the log line.
