# 1. Move the host OS web UI off ports 80 and 443

Traefik must use `80:80` and `443:443` on the host as those are the ports browsers
and Let's Encrypt reach without being told otherwise. Any OS that serves its own web UI
(TrueNAS, Synology DSM, Proxmox, OMV) ships listening on exactly those ports, so the very
first `docker compose up` for Traefik fails with `address already in use`. Do this before
anything else. Once the stack is running, a mistake here locks you out of both the host UI
and every service behind the proxy at the same time.

On TrueNAS SCALE, set web interface ports:

| Setting                  | Value |
| ------------------------ | ----- |
| Web Interface HTTP Port  | `81`  |
| Web Interface HTTPS Port | `444` |

Applying this drops your current session. Reconnect at `http://<truenas-host>:81` and verify before
continuing. The rest of this stack already assumes those two numbers: Traefik routes
`nas.${DOMAIN_LOCAL}` to `${HOST_IP}:81` ([traefik/compose.yaml](../traefik/compose.yaml)) and
Homepage's TrueNAS widget polls `${HOST_IP}:444`. If you pick different ports, change them
there too.

Confirm nothing else is holding the ports before moving on:

```bash
sudo ss -tlnp '( sport = :80 or sport = :443 )'
```

And confirm the output is empty.

# 2. Clone into the exact path that becomes the permanent `/repo` mount

```bash
cd /mnt/<pool>/appdata/deploy-agent
git clone https://github.com/doyoungp00/homelab.git repo
cp /path/to/age.key ./age.key   # Copied manually, never via git
chmod 600 age.key
```

# 3. Decrypt `WEBHOOK_SECRET` to plaintext, once, by hand

TrueNAS SCALE's host OS has a read-only root filesystem — you can't `curl`/install `sops`
onto the bare host. Run the decrypt inside a throwaway container built from the `deploy-agent` image
instead, which already bakes in `sops`. `docker compose run` reuses the same `/repo` and
`age.key` volume mounts already defined in `compose.yaml`, so nothing extra needs wiring up.

```bash
cd /mnt/<pool>/appdata/deploy-agent/repo

sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent build

sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent \
  run --rm --entrypoint python3 --workdir /repo deploy-agent \
  -m scripts.decrypt_secrets --services deploy-agent
```

`--entrypoint python3` overrides the image's default (which normally launches `agent.py`),
and `--workdir /repo` makes `scripts` resolve as a package the same way it does everywhere
else in this repo. Every `docker compose` invocation in this file needs the same
`sudo MNT_APPDATA=... DOCKER_CONFIG=...` prefix — each `sudo` call is a fresh process that
won't see a plain `export` from earlier in the session.

To rotate the secret instead of just bootstrapping it, same idea — decrypt, edit, re-encrypt,
all inside the same throwaway container:

```bash
sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent \
  run --rm --entrypoint python3 --workdir /repo deploy-agent \
  -m scripts.decrypt_secrets --services deploy-agent   # writes .env

echo "WEBHOOK_SECRET=$(openssl rand -hex 24)" > services/deploy-agent/.env

sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent \
  run --rm --entrypoint python3 --workdir /repo deploy-agent \
  -m scripts.encrypt_secrets --services deploy-agent   # writes secret.sops.env back

git add services/deploy-agent/secret.sops.env
git commit -m "rotate deploy-agent webhook secret" && git push
```

## Where `WEBHOOK_SECRET` is used

It authenticates the manual-trigger endpoint in [agent.py](agent.py)'s `Handler.do_POST`: a
`POST /deploy` request is only honored if its `X-Deploy-Secret` header matches
`WEBHOOK_SECRET` (read from the environment at startup), otherwise it gets a 401. The port is
LAN-only with no TLS, so this header is the only thing stopping another device on the LAN from
forcing a redeploy — it gates _who can trigger_, not any data in transit.

Easiest way to trigger a deploy: open `http://<truenas-host>:9000/` in a browser. It's a small
GUI served by `agent.py` itself — pick a service (or leave it on "All services"), enter the
secret, and click Deploy. Watch the result in Dozzle or `docker logs deploy-agent`.

The same thing via curl, e.g. for scripting or cron (force-recreates every service):

```bash
curl -X POST -H "X-Deploy-Secret: <value>" http://<truenas-host>:9000/deploy
```

To instead only apply services whose directory actually changed (same targeted
behavior as a poll tick), add `?force=false`:

```bash
curl -X POST -H "X-Deploy-Secret: <value>" "http://<truenas-host>:9000/deploy?force=false"
```

To redeploy exactly one named service — always forced, regardless of `?force=` —
without touching anything else, add `?service=<name>`:

```bash
curl -X POST -H "X-Deploy-Secret: <value>" "http://<truenas-host>:9000/deploy?service=nextcloud-aio"
```

# 4. Launch

```bash
sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent up -d --build --force-recreate
```

`--force-recreate` matters here: `docker compose up` decides whether to recreate a container by
hashing the resolved compose config, not by checking whether a rebuilt image's digest actually
changed. Since `compose.yaml` itself rarely changes between `agent.py` edits, `--build` alone can
produce a new image that `up` then leaves completely unused, silently keeping the old container
running on the old code.

# 5. Authentik and logins

Most logins go through Authentik: a login wall in front of the admin tools, OIDC for apps with their own accounts, and LDAP for Jellyfin. The repo rebuilds Authentik's structure (groups, providers, applications, the LDAP flow) from `services/authentik/blueprints/`, and the client IDs and secrets in sops are reused, so both sides of every login still match. What isn't in the repo depends on whether appdata comes back.

Either way, `auth.${DOMAIN_PUBLIC}` must resolve before any login works: publicly (ddclient), and from inside the LAN and from containers (hairpin NAT or an AdGuard rewrite). Until Authentik is up, every route behind the login wall, this agent's own page included, returns an error instead of a login page. That's expected, and the agent keeps polling and deploying regardless.

## Restoring appdata from a backup

Authentik's database brings back users, passwords, MFA, app passwords, user attributes, and the LDAP outpost's token, and each app's database brings back its own OIDC settings. Only check that `${MNT_APPDATA}/authentik/data` is still owned by `568` (`sudo chown -R 568:568 /mnt/<pool>/appdata/authentik/data`).

## Starting without appdata

Before the first deploy, create `${MNT_APPDATA}/authentik/data` owned by `568`. Then, after it:

1. Set the `akadmin` password at `https://auth.${DOMAIN_PUBLIC}/if/flow/initial-setup/`, and keep that account as the way back in.

2. Check that **Customization → Blueprints** shows every `homelab - …` blueprint as successful.

3. Recreate each person as in "Adding a person" in the Authentik README: username, email, groups, MFA, and a `nextcloud_uid` attribute where their Nextcloud ID differs from their username.

4. The new LDAP outpost has a new token, so the `LDAP_OUTPOST_TOKEN` in `authentik/secret.sops.env` is stale. Copy the new one from **Applications → Outposts → LDAP → View Deployment Info**, push it, and let the agent redeploy Authentik. Everyone creates a new Jellyfin app password.

5. In each app that starts empty, create its first admin with a password first; most can't be configured before they have one. That account is also the app's way back in if Authentik is down. Then set up the app's side of OIDC from its README ("Setting up OIDC") for Immich, Cleanuparr (arr-stack README), Dockhand, BookOrbit, and Nextcloud. Karakeep, wg-easy, Dawarich, and Vaultwarden read theirs from `compose.yaml` and need nothing.

## If Authentik is down

Password logins keep working wherever they're still enabled, and `akadmin` is a local account. Pages behind the login wall stay unreachable; to open them in an emergency, revert the `traefik.http.routers.<name>.middlewares=authentik@docker` labels and push, since the agent deploys from git without Authentik.
