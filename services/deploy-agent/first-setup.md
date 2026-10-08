# 1. Clone into the exact path that becomes the permanent `/repo` mount

```bash
cd /mnt/<pool>/appdata/deploy-agent
git clone https://github.com/doyoungp00/homelab.git repo
cp /path/to/age.key ./age.key   # Copied manually, never via git
chmod 600 age.key
```

# 2. Decrypt `WEBHOOK_SECRET` to plaintext, once, by hand

```bash
cd /mnt/<pool>/appdata/deploy-agent/repo
export SOPS_AGE_KEY_FILE=/mnt/<pool>/appdata/deploy-agent/age.key
python -m scripts.decrypt_secrets --services deploy-agent
```

To rotate the secret instead of just bootstrapping it:

```bash
python -m scripts.decrypt_secrets --services deploy-agent   # writes .env
echo "WEBHOOK_SECRET=$(openssl rand -hex 24)" > services/deploy-agent/.env
python -m scripts.encrypt_secrets --services deploy-agent   # writes secret.sops.env back
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
docker compose -f services/deploy-agent/compose.yaml --project-directory services/deploy-agent up -d --build
```
