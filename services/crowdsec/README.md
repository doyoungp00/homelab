# What it's for

CrowdSec is an intrusion detection engine. It reads Traefik's access log, detects malicious behaviour (scanners, brute force, exploit attempts), and bans the offending IPs. It also runs an AppSec(WAF) listener that inspects each request before it reaches a backend.

[Check out the project](https://www.crowdsec.net)

# Why it's needed

1. Some services are exposed to the internet through `DOMAIN_PUBLIC` (Nextcloud, Jellyfin, Navidrome). CrowdSec coupled with the bouncer plugin in Traefik blocks known bad IPs and suspicious requests before they reach those services.

2. The bouncer middleware is applied on Traefik's `websecure` entrypoint rather than per router, so every service behind Traefik is covered automatically, including ones added later.

# Notes

1. `/etc/crowdsec` is not persisted. Hub collections are installed at every boot from the `COLLECTIONS` environment variable, so anything installed by hand with `cscli` is lost on restart. Add it to `COLLECTIONS` instead.

2. `acquis.yaml` is synced into appdata by `hooks.py` on every deploy. Edit the copy in this repo, not the one in appdata.

3. LAN and WireGuard clients (RFC1918 addresses) skip both the bouncer and the WAF. This is set in Traefik's labels to avoid locking yourself out of the admin UIs from inside the network.

4. If the public domains are proxied through Cloudflare (orange cloud), the real client IP arrives behind a Cloudflare edge IP. Without trusting Cloudflare's ranges in Traefik, CrowdSec will ban Cloudflare and all public services go dark. See the commented lines in Traefik's `compose.yaml`.

5. The bouncer fails open. If CrowdSec is down, traffic still flows, but no new bans are made. This is a deliberate decision that prioritizes network connectivity before security.
