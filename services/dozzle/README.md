# What it's for

Dozzle is a real-time log viewer for Docker containers.

[Check out the project](https://dozzle.dev)

# Why it's needed

Logs for every container are available in the browser, without needing to SSH into the host and run `docker logs`. This is also where Deploy Agent's output is checked after triggering a deploy.

# Notes

1. Container actions (start, stop, restart) and shell access are enabled, and no authentication is configured. Anyone who can reach Dozzle can control containers and open a shell in them. Enable `DOZZLE_AUTH_PROVIDER` if that isn't acceptable.

2. Dozzle only reads logs from Docker. It doesn't store them, so logs are gone once Docker rotates them or a container is removed.
