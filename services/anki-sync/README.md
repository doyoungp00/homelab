# What it's for

Anki Sync Server Enhanced packages Anki's official sync server with a few extras on top, such as scheduled backups. The Anki desktop app, AnkiDroid, and AnkiMobile sync to it instead of to AnkiWeb.

[Check out the project](https://github.com/chrislongros/anki-sync-server-enhanced)

# Why it's needed

1. Decks, review history, and media are kept on the NAS instead of on AnkiWeb, and still sync between every device.

2. AnkiWeb deletes collections that go unused for a long time and limits collection size. A self-hosted server has neither limit.

# Notes

1. Accounts are set by `ANKI_SYNC_USER1` in `secret.sops.env`, as `user:password`. To add more people, add `ANKI_SYNC_USER2` and so on to `secret.sops.env`, and a matching `SYNC_USER2=${ANKI_SYNC_USER2:?...}` line to `compose.yaml`. If a password contains `$`, single-quote the value, or compose interpolation will eat it (see the ntfy README).

2. To point a client at the server, set the sync server in its preferences to `https://anki-sync.<DOMAIN_LOCAL>/`, then log in with the user and password above. On desktop it's under Preferences → Syncing → Self-hosted sync server, and in AnkiDroid it's the custom sync server setting.

3. The server is only reachable through `DOMAIN_LOCAL`, so clients outside the LAN need to be connected through WireGuard to sync. Reviews done offline sync the next time the device can reach the server.

4. The image tag is pinned to an Anki release (`26.05`). Clients sync fine against a server that's a little older, but bump the tag along with the clients after a major Anki release.

5. `${MNT_APPDATA}/anki-sync/data` holds every user's collection and media. `BACKUP_ENABLED` copies it into `${MNT_APPDATA}/anki-sync/backups` every night at 03:00 and keeps 7 days of copies. Those copies sit on the same pool, so they guard against a bad sync, not against losing the disk.

6. The image's optional dashboard (`:8081`) and Prometheus metrics (`:9090`) are left off. The dashboard has no login unless `DASHBOARD_AUTH` is set.
