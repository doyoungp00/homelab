# What it's for

cloudflare-ddns keeps Cloudflare DNS records pointed at the network's public IP, updating them whenever it changes.

[Check out the project](https://github.com/favonia/cloudflare-ddns)

# Why it's needed

Most residential internet connections don't have a static IP. Public services under `DOMAIN_PUBLIC` and the WireGuard endpoint (`WG_HOST`) need DNS records that follow the public IP, or they become unreachable whenever the ISP assigns a new one.

# Notes

1. `CLOUDFLARE_API_TOKEN` in `secret.sops.env` is a Cloudflare API token (not the global API key) with **Zone → DNS → Edit** on the `DOMAIN_PUBLIC` zone.

2. The records it manages are the `DOMAINS` list in `compose.yaml`. A new public hostname has to be added there as well as to its Traefik router, or it never gets a DNS record. `nas.` isn't a Traefik route: it's the WireGuard endpoint.

3. Records are DNS only (`PROXIED=false`). WireGuard is UDP, which Cloudflare's proxy doesn't carry; proxied traffic would reach CrowdSec from Cloudflare's IPs (see the Traefik README); and the proxy caps uploads at 100 MB. `PROXIED` only applies to records it creates, so an existing record's proxy status has to be changed in Cloudflare's dashboard.

4. IPv6 is off (`IP6_PROVIDER=none`), since nothing here listens on IPv6. That leaves any existing AAAA records alone rather than deleting them; remove stale ones in Cloudflare's dashboard.

5. It checks the IP every 5 minutes. The image has no health command and no web UI, so Gatus checks the outcome instead: that `nas.${DOMAIN_PUBLIC}` resolves through a public resolver (1.1.1.1), with an ntfy alert if it stops. That catches a missing record, not one left on an old IP; check its logs in Dozzle if a hostname seems to point at the wrong place.
