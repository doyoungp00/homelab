# What it's for

Traefik is a reverse proxy that routes requests to each service by hostname and handles TLS certificates.

[Check out the project](https://traefik.io/traefik)

# Why it's needed

1. Every service is reached by a hostname like `<service>.example.com` over HTTPS, instead of `<ip>:<port>`. Routes are discovered from `traefik.*` labels on each container.

2. Certificates come from Let's Encrypt through Cloudflare's DNS challenge, so even LAN-only services get valid certificates without opening any ports.

3. All traffic on `websecure` passes through the CrowdSec bouncer and WAF.

4. It also routes `nas.example.com` to TrueNAS's own web UI on `${HOST_IP}:81`.

# Known caveats

1. Traefik uses ports 80 and 443, so ensure the host isn't already using them. For example, configure TrueNAS to serve its web UI at ports 81 and 444.

2. The dashboard is only available through the `traefik` router, with basic auth. The insecure API on port 8080 is disabled, since it would expose the full config (including `CROWDSEC_LAPI_KEY`) to every container on `proxy`.

3. The basic auth hash uses `{SHA}` rather than bcrypt, because a `$` in the hash would be eaten by compose interpolation. That's only acceptable because the password is long and random.

4. If the public domains are proxied through Cloudflare, Cloudflare's IP ranges must be trusted, or CrowdSec will ban Cloudflare itself. See the commented lines in `compose.yaml`.

5. Access logs go to stdout for CrowdSec to read, and are capped at three 10MB files by the `logging` block.
