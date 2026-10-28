# What it's for

Vaultwarden is a lightweight, self-hosted server for storing passwords, passkeys, TOTP codes, and secure notes. It implements the Bitwarden API, so the official Bitwarden apps and browser extensions work with it.

[Check out the project](https://github.com/dani-garcia/vaultwarden)

# Why it's needed

1. Credentials are kept on the NAS instead of a third-party cloud, while still syncing across every device through the official Bitwarden clients.

2. Features that are paid in Bitwarden, like TOTP codes, file attachments, and organizations for sharing items, are available for free.

# Notes

1. Vaultwarden is only reachable through `DOMAIN_LOCAL`, so clients outside the LAN need to be connected through WireGuard to sync. The Bitwarden clients keep an offline copy of the vault, so saved items are still readable without a connection, but new or changed items won't sync until the tunnel is up.

2. `DOMAIN` must match the address the vault is opened at, `https://` included. Vaultwarden uses it to build links and to validate WebAuthn and passkey logins, which fail on a mismatch. The Bitwarden clients and web vault also refuse to work over plain HTTP, which is why it's served through Traefik with a valid certificate.

3. Sign-ups are open by default (`SIGNUPS_ALLOWED` is unset), so anyone who can reach the server can create an account. Create the accounts that are needed, then set `SIGNUPS_ALLOWED=false` and redeploy.

4. The admin panel at `/admin` is disabled because `ADMIN_TOKEN` isn't set. To enable it, generate an Argon2 hash with `docker exec -it vaultwarden /vaultwarden hash` and put it in `secret.sops.env`, single-quoted, since the hash contains `$` and would otherwise be eaten by compose interpolation (see the ntfy README).

5. No SMTP server is configured, so email verification, password hints by email, emailed 2FA codes, and organization invite emails don't work. Invited users can still be confirmed from the web vault.

6. `${MNT_APPDATA}/vaultwarden/data` holds the SQLite database, attachments, and the RSA key used to sign login tokens. It isn't reproduced from this repo, and losing it means losing every vault. Back it up, and make sure the backup is reachable without the password manager itself.

7. Login can go through SSO against the `vaultwarden` application in Authentik (`authentik/blueprints/vaultwarden.yaml`), open to the `admins` and `family` groups. SSO replaces only the login step: the master password still decrypts the vault, and isn't stored in Authentik. Both sides are in this repo: Vaultwarden reads its SSO settings from `SSO_*` variables. `VAULTWARDEN_OIDC_CLIENT_ID` and `VAULTWARDEN_OIDC_CLIENT_SECRET` have to be set to the same values in both `vaultwarden/secret.sops.env` and `authentik/secret.sops.env`.

8. A first SSO login links to the existing account with the same email, but only because the provider uses the shared "verified" email mapping in `authentik/blueprints/scope-mappings.yaml`; Vaultwarden refuses to link an unverified email. After that it matches by Authentik's issuer and subject, so a later email change doesn't move the link. `SSO_AUTH_ONLY_NOT_SESSION` keeps Vaultwarden's own session lifetime, since Authentik's 5-minute access tokens clash with the clients' expiry checks. `SSO_ONLY` stays off, so password login still works if Authentik is down.
