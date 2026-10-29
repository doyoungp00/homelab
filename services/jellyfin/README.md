# What it's for

Jellyfin is a media server for streaming movies and TV shows.

[Check out the project](https://jellyfin.org)

# Why it's needed

1. Media managed by the Arr Stack can be streamed to phones, TVs, and browsers, both at home and remotely through `DOMAIN_PUBLIC`.

2. Hardware transcoding through the host's GPU (`/dev/dri`) lets lower-powered clients play formats they don't support natively.

# Notes

1. The `render` (`107`) and `video` (`44`) group IDs in `group_add` are specific to this host. Check them with `getent group render video` on a new host, or hardware transcoding will fail.

2. Only `Movies` and `TV Series` are mounted. Other libraries need their own volume.

3. Jellyfin is exposed publicly, so it's covered by CrowdSec. Use strong passwords for every user.

4. Logins go through Authentik over LDAP (the `authentik-ldap` outpost; see `authentik/blueprints/ldap.yaml`), so every client keeps its own login screen. The password is an Authentik **app password**, not the person's main one: LDAP can't ask for MFA, so the LDAP bind flow accepts app passwords only. Each person gets one from Authentik (see note 10 in the Authentik README) and uses it in every Jellyfin app, and in Seerr, which signs in through Jellyfin. Quick Connect saves typing it on TVs. The plugin settings live in Jellyfin's config, not this repo; see "Setting up LDAP" below.

# Setting up LDAP

Authentik's side (the LDAP flow, the `ldap-search` account, the outpost) is created by `authentik/blueprints/ldap.yaml` and the `authentik-ldap` container. Jellyfin's side is set up by hand once, on a fresh install or after its config is lost.

1. Create a local admin that isn't tied to Authentik (e.g. `jellyfin-admin`, Authentication Provider left as Default), and keep its password in Vaultwarden. It's the way back in if Authentik is down.

2. **Dashboard → Plugins → Catalog**, install **LDAP Authentication**, and restart Jellyfin.

3. **Dashboard → Plugins → LDAP-Auth**, set:

   | Field                     | Value                                                                                                                        |
   | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
   | LDAP Server               | `authentik-ldap`                                                                                                             |
   | LDAP Port                 | `3389`                                                                                                                       |
   | Secure LDAP / StartTLS    | Off. The traffic stays on the `proxy` Docker network.                                                                        |
   | LDAP Bind User            | `cn=ldap-search,ou=users,dc=ldap,dc=goauthentik,dc=io`                                                                       |
   | LDAP Bind User Password   | `LDAP_SEARCH_APP_PASSWORD` from `authentik/secret.sops.env`                                                                  |
   | LDAP Base DN for searches | `dc=ldap,dc=goauthentik,dc=io`                                                                                               |
   | LDAP Search Filter        | `(\|(memberOf=cn=admins,ou=groups,dc=ldap,dc=goauthentik,dc=io)(memberOf=cn=family,ou=groups,dc=ldap,dc=goauthentik,dc=io))` |
   | LDAP Admin Filter         | `(memberOf=cn=admins,ou=groups,dc=ldap,dc=goauthentik,dc=io)`                                                                |
   | LDAP Search Attributes    | `cn`                                                                                                                         |
   | LDAP Uid Attribute        | `uid`                                                                                                                        |
   | LDAP Username Attribute   | `cn`                                                                                                                         |
   | Enable User Creation      | On, so new family members get a Jellyfin user on first login                                                                 |

   Use **Save and Test LDAP Server Settings** and **Test LDAP Filters**: the filter test should list the people in `admins` and `family`.

4. For each existing user, **Dashboard → Users → (user) → Authentication Provider**, choose the LDAP provider and save. Usernames match Authentik's, so their history and settings stay. Until this is done, the plugin ignores that user: their old Jellyfin password keeps working and the app password doesn't. Leave the local admin from step 1 on Default.

5. **Dashboard → General → Quick Connect**, enable it. A TV then shows a code to approve from a phone that's already logged in.

6. Test in a private window: Authentik username plus the app password logs in, and the main Authentik password doesn't.
