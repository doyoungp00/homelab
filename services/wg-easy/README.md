# What it's for

wg-easy is a WireGuard VPN server with a web UI for managing clients.

[Check out the project](https://github.com/wg-easy/wg-easy)

# Why it's needed

1. LAN-only services can be reached securely from outside the network, without exposing them to the internet.

2. Clients use AdGuard Home (`HOST_IP`) as their DNS server, so local domains resolve and ads are blocked even away from home.

# Notes

1. UDP port `51820` must be forwarded on the router, and `WG_HOST` must point at the public IP (kept up to date by ddclient).

2. wg-easy must stay on a single network. Its masquerade rule is pinned to `eth0`, and with a second network Docker may put the default route on the other interface, silently breaking client traffic.

3. The `INIT_*` variables are only used on first start. Changing them afterwards does nothing. Use the web UI instead.

4. IPv6 is disabled.

5. The web UI is behind the Authentik login wall, and wg-easy's own login uses OIDC against the `wg-easy` application in Authentik (`authentik/blueprints/wg-easy.yaml`), which only the `admins` group can use. Both sides are in this repo: wg-easy reads its OIDC settings from `OAUTH_*` variables. `WG_EASY_OIDC_CLIENT_ID` and `WG_EASY_OIDC_CLIENT_SECRET` have to be set to the same values in both `wg-easy/secret.sops.env` and `authentik/secret.sops.env`.

6. `OAUTH_AUTO_REGISTER` is off, because every wg-easy user is an administrator. An existing account is linked once: log in with its password, open the account page (`/me`), and click Authentik under External authentication. Until then, Sign in with Authentik fails with "Auto registration is disabled". wg-easy also rejects any login whose `email_verified` claim is false, so the blueprint gives it its own email scope mapping that always sends true. Keep the password login (`INIT_USERNAME`) as a way back in; Homepage's widget uses it too.
