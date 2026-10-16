# What it's for

Deploy Agent is a custom CI/CD service that keeps the running stack in sync with this repo.

- Polls the repo every 15 minutes (`POLL_INTERVAL_SECONDS`) and runs `scripts/deploy.py`, which applies `docker compose up -d` to every service whose directory changed since the last deploy.
- Decrypts each service's `secret.sops.env` with sops before deploying.
- Runs each service's `hooks.py` (if present) to place config files under its appdata before the container starts. See `scripts/hooks.py`.
- Serves a small web GUI and a `POST /deploy` endpoint for triggering a deploy on demand, protected by `WEBHOOK_SECRET`.

# Why it's needed

Changes are made by pushing to `main`, not by logging into the NAS. The agent removes the need to SSH in, pull, decrypt secrets, and run compose for each changed service by hand.

# Known caveats

1. The agent can't redeploy itself. Changes to this directory have to be applied by hand with `docker compose up -d --build --force-recreate`. `--force-recreate` is required, or the rebuilt image goes unused. See [first-setup.md](first-setup.md).

2. Initial setup (cloning the repo, copying `age.key`, decrypting `WEBHOOK_SECRET`) is a manual process. Follow [first-setup.md](first-setup.md).

3. The agent has the Docker socket and write access to all of appdata, which makes it effectively root on the host. Hooks are given only their own service's appdata directory, but that's a convenience, not a sandbox.

4. A first-ever clone force-redeploys every service, which can take several minutes before the GUI responds.

5. The sops binary is downloaded for `amd64` only.
