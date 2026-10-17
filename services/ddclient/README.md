# What it's for

ddclient is a dynamic DNS client. It checks the network's public IP and updates DNS records whenever it changes.

[Check out the project](https://github.com/ddclient/ddclient)

# Why it's needed

Most residential internet connections don't have a static IP. Public services under `DOMAIN_PUBLIC` and the WireGuard endpoint (`WG_HOST`) need DNS records that follow the public IP, or they become unreachable whenever the ISP assigns a new one.

# Notes

1. The configuration (`ddclient.conf`) lives only in `${MNT_APPDATA}/ddclient/config`, not in this repo, since it contains DNS provider credentials. It must be recreated by hand on a new host.

2. ddclient has no web UI or health endpoint, so it isn't monitored by Gatus. Check its logs in Dozzle if a DNS record seems stale.
