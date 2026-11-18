# What it's for

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is a personal AI agent that runs all the time and is reached from chat apps (Telegram and others) or its web dashboard. [GBrain](https://github.com/garrytan/gbrain) is its long-term memory: a searchable knowledge base and graph of everything it's told to remember, plus any notes imported into it.

Together they maintain an Obsidian vault as a personal wiki, following [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): you drop sources into `raw/`, and Hermes reads them and writes and cross-links the pages in `wiki/`. You read it in Obsidian on your phone and desktop, synced through [Syncthing](../syncthing/README.md).

# Why it's needed

An agent that stays online can take requests from a phone, run scheduled jobs, and remember things across conversations, without a computer left running. GBrain keeps that memory in a database on the NAS rather than in a vendor's cloud.

# Notes

1. Four containers: `hermes` (the agent and its dashboard), `gbrain` (an HTTP MCP server, built from `Dockerfile` at a pinned release), `gbrain-sync` (re-indexes the vault into gbrain every 15 minutes), and `gbrain-db` (Postgres with pgvector). gbrain and its database are only on the stack's own `hermes-agent` network; Hermes is gbrain's only client.

2. The dashboard is at `hermes.${DOMAIN_LOCAL}`, behind the Authentik login wall and then Hermes' own login (`HERMES_DASHBOARD_BASIC_AUTH_*` in `secret.sops.env`). Hermes refuses to serve the dashboard on a network address without a login of its own, and the dashboard holds API keys and can drive the agent.

3. Hermes keeps everything (model provider keys, chat platform tokens, `config.yaml`, memory, sessions, skills) in `${MNT_APPDATA}/hermes-agent/hermes`, which it manages itself. Only the dashboard login and the gbrain token are in this repo.

4. The agent can run shell commands, inside its container. That container is on `proxy` (for Traefik), so the agent can reach every service on that network directly, including ones whose API has no login of its own (Bazarr, Frigate's port 5000). Keep chat access restricted to yourself (`TELEGRAM_ALLOWED_USERS` or the platform's equivalent).

5. gbrain connects to Postgres with `sslmode=disable`. It requires TLS to any non-local database by default, and this one is only reachable on the stack's network.

6. gbrain serves its `starter` tool set (29 tools) rather than all 127, to keep the model's context small. The rest stay reachable through its `request_tools` tool.

7. `hooks.py` creates `${MNT_APPDATA}/hermes-agent/gbrain` and the vault owned by `568` before deploying. Docker would otherwise create them as root: gbrain fails at startup with `EACCES`, and Hermes and Syncthing can't write the vault.

8. The vault is at `${MNT_APPDATA}/hermes-agent/vault`, mounted at `/vault` (read-write in `hermes`, read-only in `gbrain` and `gbrain-sync`). `hooks.py` seeds it once from `vault/`: the schema Hermes follows (`AGENTS.md`), `index.md`, `log.md`, and the `raw/` and `wiki/` folders. After that, the repo never touches it again; edit `AGENTS.md` in the vault itself to change the conventions.

9. The vault is a plain folder, not a git repository: gbrain imports it by reading the files (unchanged ones are skipped by content hash), and Syncthing's file versioning stands in for history. Pages deleted from the vault stay in gbrain until removed there (`gbrain delete`). gbrain only takes this plain-folder path when `/vault` exists in the container running the command, which is why `gbrain` mounts it too; without it, sync fails with `Not inside a git repository: /vault`.

10. To upgrade gbrain, bump `GBRAIN_VERSION` in `Dockerfile` to the stable channel's current release ([VERSION on its stable branch](https://github.com/garrytan/gbrain/blob/stable/VERSION)). Hermes follows `:latest`.

# Setting up

After the first deploy, once per fresh install:

1. **Configure Hermes**: model provider key, model, and a chat platform. For Telegram, the dashboard's **Messaging → Telegram → Create with QR** sets up the bot and restricts it to you.

   ```sh
   docker exec -it hermes hermes setup
   ```

2. **Trust Traefik**, so the dashboard honors `X-Forwarded-Proto: https`:

   ```sh
   docker exec hermes hermes config set dashboard.trusted_proxies '["172.16.25.0/24"]'
   docker restart hermes
   ```

3. **Initialize gbrain** once, keyword search only (no embedding provider, so no notes are sent anywhere). `sync` fails until this is done:

   ```sh
   docker exec gbrain sh -c 'gbrain init --url "$GBRAIN_DATABASE_URL" --no-embedding --non-interactive'
   ```

4. **Mint gbrain's token for Hermes.** It's shown once:

   ```sh
   docker exec gbrain gbrain auth create hermes --scopes read,write
   ```

   Add it as `GBRAIN_MCP_TOKEN` to `secret.sops.env` (decrypt, edit `.env`, encrypt; see the root README) and push. The redeploy hands it to Hermes.

5. **Connect Hermes to gbrain.** The header refers to the variable, so the token never sits in `config.yaml`:

   ```sh
   docker exec hermes hermes config set mcp_servers.gbrain '{"url": "http://gbrain:3131/mcp", "headers": {"Authorization": "Bearer ${GBRAIN_MCP_TOKEN}"}, "connect_timeout": 60}'
   docker exec hermes hermes mcp test gbrain
   ```

6. **Register the vault with gbrain.** The link setting lets Obsidian-style `[[page]]` links resolve across folders:

   ```sh
   docker exec gbrain gbrain sources add wiki --path /vault --federated
   docker exec gbrain gbrain config set link_resolution.global_basename true
   docker exec gbrain gbrain sync --all
   ```

   From then on `gbrain-sync` keeps it current.

7. **Tell the agent about both.** Agents seldom use a memory or a wiki nobody told them about, and gbrain's own `gbrain setup hermes` can't write this from a separate container. Add to `SOUL.md` in Hermes' data directory, e.g.: *"You maintain my wiki at /vault. Before working on it, read /vault/AGENTS.md and follow it. Before answering anything, search GBrain (mcp__gbrain__recall, found with tool_search) for what you already know; save anything worth keeping with mcp__gbrain__remember."*

8. **Set up Syncthing and Obsidian** on your devices: see the [Syncthing README](../syncthing/README.md#setting-up-the-vault).
