# What it's for

AdGuard Home is a local DNS server with ad blocking at the network level.

[Check out the project](https://github.com/AdguardTeam/AdguardHome)

# Why it's needed

1. DNS based network level ad blocking cuts down on ads shown on devices, especially on mobile devices and smart TVs. Although not perfect, it still reduces the amount of ads pushed through to devices.

2. With the DNS rewrite feature, local domains can resolve to local network addresses. This is how the `DOMAIN_LOCAL` environment works. Clients that use AdGuard Home as their DNS server can connect to `<service>.example.com`. A rewrite rule that covers `*.example.com` will forward it to Traefik for reverse proxy.

# Known caveats

By being on the `proxy` network, traffic from other containers will all show as one client (e.g. `172.16.25.1`, which is `proxy`'s gateway IP), obfuscating which container is making which request. This is an architectural limit on Docker's side.
