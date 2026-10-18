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

2. When `gluetun` is recreated (e.g. on an image update), the containers sharing its network namespace lose connectivity and must be restarted as well. Their `depends_on` doesn't set `restart: true`, so this doesn't happen automatically.

3. Gluetun sets qBittorrent's listening port to the forwarded VPN port through qBittorrent's API on `127.0.0.1:8080`. This requires "Bypass authentication for clients on localhost" to be enabled in qBittorrent's WebUI settings, otherwise the port is never applied.

4. Flaresolverr is not routed through Gluetun. Indexer requests Prowlarr sends through Flaresolverr go out from the home IP, not the VPN.

5. `/downloads` and the media folders (`/data/movies`, `/data/tv`) are separate bind mounts, so Radarr and Sonarr can't hardlink. Each import is a full copy, using double the space while a torrent is still seeding. Mounting a single shared parent directory into qBittorrent, Radarr, and Sonarr would allow hardlinks.

6. qBittorrent, Radarr, and Sonarr must all mount the torrent folder at the same path (`/downloads`). Otherwise Radarr and Sonarr can't find the files qBittorrent reports as finished.

7. If the VPN connection drops, containers behind Gluetun lose internet access entirely rather than falling back to the home IP. This is intended, as it prevents leaks.
