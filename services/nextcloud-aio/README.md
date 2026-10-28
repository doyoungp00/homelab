# What it's for

Nextcloud is a self-hosted cloud storage and collaboration platform. Nextcloud All-in-One (AIO) is its official Docker installation, which manages Nextcloud and its supporting services for you.

[Check out the project](https://github.com/nextcloud/all-in-one)

# Why it's needed

Files, contacts, and calendars sync across devices and can be shared with others, while staying on the NAS instead of a third-party cloud.

# Notes

1. Only the mastercontainer is defined in `compose.yaml`. It creates every other container (Apache, database, Redis, etc.) itself, so those aren't managed by this repo or Deploy Agent. Updates and backups are done through the AIO interface.

2. The AIO interface is on port `8080` of the host, with a self-signed certificate. The Nextcloud web UI is served by the dynamically created `nextcloud-aio-apache` container, which joins the `proxy` network through `APACHE_ADDITIONAL_NETWORK`.

3. `NEXTCLOUD_DATADIR` must not be changed after the initial installation.

4. WebDAV sync needs encoded slashes and other characters allowed. This is set globally on Traefik's `websecure` entrypoint, since there is no per-router option.

5. Login can go through OIDC against the `nextcloud` application in Authentik (`authentik/blueprints/nextcloud.yaml`), open to the `admins` and `family` groups, using Nextcloud's `user_oidc` app. Nextcloud's side is in its database, set with `occ`; see "Setting up OIDC" below. Accounts are matched by user ID, sent as a `nextcloud_uid` claim: the person's `nextcloud_uid` attribute in Authentik if set, otherwise their Authentik username. If neither equals their Nextcloud user ID, they get a new, empty account. Nextcloud isn't behind the login wall: the desktop and mobile clients, WebDAV, and public share links need to reach it directly.

# Setting up OIDC

Authentik's side (provider, redirect URIs, who may log in) is created by `authentik/blueprints/nextcloud.yaml`. Nextcloud's side is stored in its database and has to be set up once, on a fresh install or after restoring a backup from before this was done. Run `occ` inside the Nextcloud container:

```
docker exec --user www-data -it nextcloud-aio-nextcloud php occ <command>
```

1. Run an AIO backup from the AIO interface first.

2. Add `NEXTCLOUD_OIDC_CLIENT_ID` and `NEXTCLOUD_OIDC_CLIENT_SECRET` to `authentik/secret.sops.env` (e.g. `openssl rand -hex 20` and `openssl rand -hex 48`), deploy, and check that **Customization → Blueprints** in Authentik shows `homelab - nextcloud` as successful.

3. Check every Nextcloud user ID (`occ user:list`) against the Authentik usernames. A user ID can't be renamed in Nextcloud, so for anyone whose ID differs, set it on their Authentik user instead: **Directory → Users → (user) → Edit → Attributes**, add `nextcloud_uid: <their Nextcloud user ID>`. Do this before they first log in with Authentik.

4. Install the app and create the provider:

   ```
   occ app:install user_oidc
   occ user_oidc:provider Authentik \
       --clientid="<NEXTCLOUD_OIDC_CLIENT_ID>" \
       --clientsecret="<NEXTCLOUD_OIDC_CLIENT_SECRET>" \
       --discoveryuri="https://auth.${DOMAIN_PUBLIC}/application/o/nextcloud/.well-known/openid-configuration" \
       --scope="openid email profile nextcloud" \
       --unique-uid=0 \
       --mapping-uid=nextcloud_uid \
       --mapping-display-name=name \
       --mapping-email=email
   ```

   `--unique-uid=0` and `--mapping-uid=nextcloud_uid` are what make existing accounts match: by default user_oidc stores a hash of the provider and user ID instead, which never equals an existing user. The `nextcloud` scope is what makes Authentik send the `nextcloud_uid` claim. With that off, soft auto-provisioning (on by default) signs a matching login into the existing user and creates new users for everyone else.

5. Test **Log in with Authentik** in a private window, and check the files are the existing ones. The password login form stays available (`allow_multiple_user_backends`), and is the way back in if Authentik is down.

6. Desktop and mobile clients use Nextcloud's browser login, which now offers the Authentik button. Existing app passwords keep working.
