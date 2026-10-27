# What it's for

slskd is a Soulseek client with a web UI, for searching and downloading from the Soulseek peer-to-peer network.

[Check out the project](https://github.com/slskd/slskd)

# Why it's needed

The Arr Stack has no indexer for books and music. Soulseek is a separate network built around it, and is the practical way to find releases the usual indexers don't carry, which can then be moved into each library.

# Notes

1. slskd's own web login is disabled (`SLSKD_NO_AUTH`). The login is the Authentik wall on the `slskd` router, which only admits the `admins` group. This holds only while `slskd.yml` has no `web.authentication` section: YAML loads after the environment, so a section written there (e.g. by changing settings from the web UI) quietly takes precedence. Anything on the `proxy` network can reach `slskd:5030` without logging in.

2. `SLSKD_SLSK_USERNAME` and `SLSKD_SLSK_PASSWORD` are the Soulseek network login, and are optional. Without them slskd starts and serves its UI as usual, but never connects to the network.

3. Remote configuration writes to `slskd.yml` under `${MNT_APPDATA}/slskd`, which isn't in git. Shares, filters, and limits changed from the web UI live only on the NAS, and aren't reproduced by a redeploy or restored from this repo. `SLSKD_REMOTE_CONFIGURATION=true` also means anyone who reaches the UI can rewrite the entire configuration.

4. `PATH_SLSKD_SHARED`, `PATH_SLSKD_DOWNLOADS`, and `PATH_SLSKD_INCOMPLETE_DOWNLOADS` must all exist on the NAS and be writable by `568` before the first deploy. slskd refuses to create any of them, and Docker creates a missing bind mount source as `root`, which slskd then can't write to. The share is mounted read-only, since slskd only ever reads from it.

5. Keep `PATH_SLSKD_INCOMPLETE_DOWNLOADS` and `PATH_SLSKD_DOWNLOADS` on the same pool. They're separate mounts, so if they're on different pools, finishing a file is a copy across pools rather than a rename.

6. Shares are scanned at startup and then never again. Files added to `PATH_SLSKD_SHARED` from outside slskd stay invisible to the network until the container restarts or a scan is triggered from the web UI. `SLSKD_SHARE_CACHE_RETENTION`, in minutes, turns on periodic rescans.

7. Port `50300` isn't published, so the Soulseek network can't open incoming connections to the client. Searching and downloading still work, since those connections go outward. Publish the port and forward it at the router to be reachable directly.

8. slskd is not routed through Gluetun. Unlike qBittorrent and Prowlarr, it sits on `proxy` directly, so its Soulseek traffic goes out from the home IP rather than the VPN.

9. The API key in `compose.yaml` is restricted to the `proxy` subnet, which every container on that network shares, Traefik included. slskd deliberately ignores `X-Forwarded-For`, so a request arriving through the reverse proxy is indistinguishable from Homepage's. The key's `ReadOnly` role, not its CIDR, is what bounds what it can do.
