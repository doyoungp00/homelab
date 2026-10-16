# What it's for

Home Assistant is a home automation platform that connects and controls smart home devices locally.

[Check out the project](https://www.home-assistant.io)

# Why it's needed

Devices from different brands can be controlled from one app and automated together, and most integrations run locally without depending on each vendor's cloud.

# Known caveats

1. Home Assistant needs to trust Traefik's `X-Forwarded-For` header. Otherwise every request looks like it came from Traefik, and one failed login can IP-ban the whole household. `hooks.py` writes the trusted proxy settings into `config/.storage/http` on every deploy.

2. These settings can no longer go in `configuration.yaml`. Home Assistant 2026.9 moved the `http:` block into `.storage/http` and ignores the YAML version.

3. The container is privileged and mounts the host's D-Bus, which is needed for Bluetooth and some USB devices.
