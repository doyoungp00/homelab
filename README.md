# Homelab

Docker Compose services for a self-hosted homelab running on TrueNAS SCALE. Every service is defined in this repo, with its secrets encrypted by [sops](https://github.com/getsops/sops). Changes pushed to `main` are deployed automatically by [Deploy Agent](services/deploy-agent/README.md).

# Services

| Service                                                                                | Description                                                              |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| [AdGuard Home](services/adguardhome/README.md)                                         | Local DNS server with network-wide ad blocking and local domain rewrites |
| [Bazarr](services/arr-stack/README.md)                                                 | Fetches subtitles for movies and TV shows                                |
| [Calibre-Web](services/calibre-web/README.md)                                          | Browse, read, and convert books from a Calibre library                   |
| [Chrony](services/chrony/README.md)                                                    | Local NTP server for devices without internet access                     |
| [code-server](services/code-server/README.md)                                          | VS Code in the browser, with the tools to work on this repo              |
| [CrowdSec](services/crowdsec/README.md)                                                | Intrusion detection and WAF for Traefik                                  |
| [Dawarich](services/dawarich/README.md)                                                | Location history tracker                                                 |
| [ddclient](services/ddclient/README.md)                                                | Keeps DNS records pointed at the public IP                               |
| [Deploy Agent](services/deploy-agent/README.md)                                        | Deploys changes pushed to this repo                                      |
| [Dockhand](services/dockhand/README.md)                                                | Docker container and stack management UI                                 |
| [Dozzle](services/dozzle/README.md)                                                    | Real-time container logs                                                 |
| [File Browser](services/filebrowser/README.md)                                         | Web-based file manager for the NAS                                       |
| [Flaresolverr](services/arr-stack/README.md)                                           | Solves Cloudflare challenges for Prowlarr's indexers                     |
| [Frigate](services/frigate/README.md)                                                  | NVR with object detection for IP cameras                                 |
| [Gatus](services/gatus/README.md)                                                      | Health and uptime dashboard                                              |
| [Gatus Generator](services/gatus/README.md)                                            | Generates Gatus's config from `gatus.*` container labels                 |
| [Glances](services/glances/README.md)                                                  | Host system monitor                                                      |
| [Gluetun](services/arr-stack/README.md)                                                | VPN tunnel shared by Prowlarr, qBittorrent, and Suwayomi-Server          |
| [Home Assistant](services/homeassistant/README.md)                                     | Home automation                                                          |
| [Homepage](services/homepage/README.md)                                                | Dashboard for every service                                              |
| [Immich](services/immich/README.md)                                                    | Photo and video library                                                  |
| [Jellyfin](services/jellyfin/README.md)                                                | Movie and TV streaming                                                   |
| [Karakeep](services/karakeep/README.md)                                                | Bookmarking with page archiving and search                               |
| [MySpeed](services/myspeed/README.md)                                                  | Scheduled internet speed tests                                           |
| [Navidrome](services/navidrome/README.md)                                              | Music streaming                                                          |
| [Nextcloud AIO](services/nextcloud-aio/README.md)                                      | Cloud storage, contacts, and calendars                                   |
| [Prowlarr](services/arr-stack/README.md)                                               | Indexer manager for Radarr and Sonarr                                    |
| [qBittorrent](services/arr-stack/README.md)                                            | BitTorrent client                                                        |
| [Radarr](services/arr-stack/README.md)                                                 | Monitors, downloads, and organizes movies                                |
| [Scrutiny](services/scrutiny/README.md)                                                | Hard drive S.M.A.R.T. monitoring                                         |
| [Sonarr](services/arr-stack/README.md)                                                 | Monitors, downloads, and organizes TV shows                              |
| [Suwayomi Downloads Processor](services/suwayomi-server-downloads-processor/README.md) | Moves Suwayomi downloads into its local library                          |
| [Suwayomi-Server](services/arr-stack/README.md)                                        | Manga reader and downloader                                              |
| [Traefik](services/traefik/README.md)                                                  | Reverse proxy with automatic TLS certificates                            |
| [wg-easy](services/wg-easy/README.md)                                                  | WireGuard VPN server                                                     |

# Project structure

```
.
├── scripts/                  Deployment and secret management tooling
│   ├── deploy.py             Applies `docker compose up` to changed services
│   ├── hooks.py              Runs each service's pre/post-deploy hooks
│   ├── decrypt_secrets.py    secret.sops.env -> .env
│   ├── encrypt_secrets.py    .env -> secret.sops.env
│   └── sops_common.py        Shared sops helpers
├── services/
│   ├── shared/env/           Values shared by every service
│   │   ├── base.env          Non-secret values (PUID, PGID)
│   │   └── secret.sops.env   Shared secrets (domains, mount paths, host IP)
│   └── <service>/
│       ├── compose.yaml      The service's compose project
│       ├── secret.sops.env   Encrypted service-specific secrets (optional)
│       ├── hooks.py          Places config under appdata before deploy (optional)
│       ├── Dockerfile        For custom-built images (optional)
│       └── README.md         What it's for, why it's needed, known caveats
├── tests/                    pytest suite for scripts/
└── .sops.yaml                Encrypts every secret.sops.env with the age key
```

**Services.** Each directory under `services/` is its own compose project. All services join the external `proxy` network (pinned to `172.16.25.0/24`, created by `deploy.py` if missing), and are configured through labels:

- `traefik.*` for routing and TLS through [Traefik](services/traefik/README.md)
- `homepage.*` for a card on the [Homepage](services/homepage/README.md) dashboard
- `gatus.*` for health checks in [Gatus](services/gatus/README.md)

**Secrets.** Secrets live in `secret.sops.env` files, encrypted with an age key that is never committed. `decrypt_secrets.py` merges the shared secrets with a service's own and writes a plaintext `.env` (gitignored) next to its `compose.yaml`. To change a secret, decrypt it, edit the `.env`, then run `encrypt_secrets.py`.

```bash
export SOPS_AGE_KEY_FILE=/path/to/age.key
python -m scripts.decrypt_secrets --services <name>
python -m scripts.encrypt_secrets --services <name>
```

**Deployment.** Deploy Agent polls `main` every 15 minutes. For each service whose directory changed, it decrypts secrets, runs `hooks.py`, and runs `docker compose up -d`. Changes under `services/shared/` redeploy every service. Deploys can also be triggered by hand from its web UI.

**Tests.** Run with `pip install -r requirements-dev.txt && pytest`.

# Setup

Only Deploy Agent is set up by hand. Once it's running, it deploys every other service. Follow [first-setup.md](services/deploy-agent/first-setup.md) to:

1. Move the host OS web UI off ports 80 and 443 so Traefik can bind them.
2. Clone this repo into Deploy Agent's appdata and copy in the age key.
3. Decrypt Deploy Agent's `WEBHOOK_SECRET`.
4. Build and launch Deploy Agent.

On its first start, Deploy Agent creates the `proxy` network and force-deploys every service, which can take several minutes. Some services need extra setup afterwards. Check the **Known caveats** in each service's README.
