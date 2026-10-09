# 1. Clone into the exact path that becomes the permanent `/repo` mount

```bash
cd /mnt/<pool>/appdata/deploy-agent
git clone https://github.com/doyoungp00/homelab.git repo
cp /path/to/age.key ./age.key   # Copied manually, never via git
chmod 600 age.key
```

# 2. Decrypt `WEBHOOK_SECRET` to plaintext, once, by hand

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

To trigger a deploy manually:

```bash
curl -X POST -H "X-Deploy-Secret: <value>" http://<truenas-host>:9000/deploy
```

# 3. Launch

```bash
sudo MNT_APPDATA=/mnt/<pool>/appdata DOCKER_CONFIG=/mnt/<pool>/appdata/deploy-agent/.docker \
  docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent up -d --build
```
