# What it's for

The **Arr Stack** is a popular set of services that automate monitoring, downloading, and organizing of various media.

- **Bazarr**\
  Syncs with Radarr and Sonarr to search for missing subtitles for movies and TV shows.\
  [Check out the project](https://www.bazarr.media)

- **Cleanuparr**\
  Cleans up stalled, blocked, and malicious downloads.\
  [Check out the project](https://cleanuparr.github.io/)

- **Flaresolverr**\
  Works with Prowlarr to help resolve Cloudflare's protection for certain indexers.\
  [Check out the project](https://github.com/Flaresolverr/Flaresolverr)

- **Prowlarr**\
  Acts as a central repository for indexers, and automatically pushes them to Radarr and Sonarr. No need to set up individual indexers in each service.\
  Uses Gluetun to reach indexers that might be blocked.\
  [Check out the project](https://prowlarr.com)

- **Radarr**\
  Automates monitoring, download, and organization of movies.\
  [Check out the project](https://radarr.video)

- **Seerr**\
  Lets users browse and request movies and TV shows, then sends approved requests to Radarr and Sonarr. Syncs with Jellyfin to show what's already available.\
  [Check out the project](https://github.com/seerr-team/seerr)

- **Sonarr**\
  Automates monitoring, download, and organization of TV shows.\
  [Check out the project](https://sonarr.tv)

Additional containers run in this stack alongside the arr stack.

- **Gluetun**\
  Opens a tunnel to a VPN provider, then allows other containers to use that connection, eliminating the need for individual VPN tunnels.\
  [Check out the project](https://github.com/passteque/gluetun)

- **qBittorrent**\
  A BitTorrent client. The arr services use this as a download client, so it's included here.\
  Uses Gluetun for downloads.\
  [Check out the project](https://www.qbittorrent.org)

- **Suwayomi-Server**\
  Read and browse sources for manga.\
  Uses Gluetun to reach sources that might be blocked.\
  [Check out the project](https://github.com/Suwayomi/Suwayomi-Server)

# Why it's needed

The conventional method of searching for media, downloading it, renaming each file to fit your library, then moving and organizing each file gets tiring fast. The arr stack automates every step, and even integrates with Jellyfin to trigger a scan of newly added or modified media.

# Notes

1. Prowlarr, qBittorrent, and Suwayomi-Server use `network_mode: service:gluetun`, so they have no network identity of their own. Their Traefik and Gatus labels live on the `gluetun` container, other containers reach them at `gluetun:<port>`, and their Homepage cards are defined in Homepage's `services.yaml` instead.

2. When `gluetun` is recreated (e.g. on an image update) it gets a new container ID, and the containers sharing its network namespace are left pointing at the old one - still running, still passing their own healthchecks, with no network. `compose up` can't catch this, because it decides what to recreate by hashing the resolved compose config, and that config still reads `service:gluetun`; only the ID behind it moved. `depends_on: restart: true` wouldn't fix it either: it fires only when compose itself updates the dependency, and a _restart_ re-enters the same stale `HostConfig`. `hooks.py` handles it instead, comparing the resolved ID after each deploy and recreating whatever drifted.

3. That check is ID-based and deploy-time only. A `gluetun` that restarts in place (a crash, or `docker restart gluetun`) keeps its ID, so the hook stays quiet even though the dependents have lost their namespace just the same. Restart them by hand when that happens: `docker restart prowlarr qbittorrent suwayomi-server`.

4. Gluetun sets qBittorrent's listening port to the forwarded VPN port through qBittorrent's API on `127.0.0.1:8080`. This requires "Bypass authentication for clients on localhost" to be enabled in qBittorrent's WebUI settings, otherwise the port is never applied.

5. Flaresolverr is not routed through Gluetun. Indexer requests Prowlarr sends through Flaresolverr go out from the home IP, not the VPN.

6. `/downloads` and the media folders (`/data/movies`, `/data/tv`) are separate bind mounts, so Radarr and Sonarr can't hardlink. Each import is a full copy, using double the space while a torrent is still seeding. Mounting a single shared parent directory into qBittorrent, Radarr, and Sonarr would allow hardlinks.

7. qBittorrent, Radarr, and Sonarr must all mount the torrent folder at the same path (`/downloads`). Otherwise Radarr and Sonarr can't find the files qBittorrent reports as finished.

8. If the VPN connection drops, containers behind Gluetun lose internet access entirely rather than falling back to the home IP. This is intended, as it prevents leaks.

9. Every web UI here except Seerr and Suwayomi is behind the Authentik login wall (see the Authentik README), which only admits the `admins` group. Sonarr, Radarr, and Prowlarr are set to `External` authentication through `*__AUTH__METHOD`, so they don't ask for a second login; their APIs still require their keys. Bazarr's authentication is set to none, and qBittorrent bypasses its login for the `proxy` subnet. Cleanuparr logs in through OIDC against the `cleanuparr` application in Authentik, linked to the admin account. All three are settings in their own config, not in this repo. Anything on the `proxy` network can therefore reach these UIs directly without logging in.

10. Seerr is left out because its users log in with their Jellyfin accounts. Suwayomi is left out because manga apps connect to it directly and can't follow a login redirect, so it keeps its own login.
