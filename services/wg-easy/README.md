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
