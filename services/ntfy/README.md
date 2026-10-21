# What it's for

ntfy is a pub/sub notification server. Anything that can send an HTTP POST publishes a message to a topic, and subscribers on that topic (the phone app, a browser, a script) receive it as a push notification.

[Check out the project](https://ntfy.sh)

# Why it's needed

1. Several services detect problems but have no way to tell anyone: Gatus knows a service is down, deploy-agent knows a deploy failed, Frigate knows something moved. ntfy is the one place they all send to, so there's a single app to install and a single set of credentials to manage.

2. An alert is only worth sending if it arrives while you're away from the LAN. Reaching ntfy over `DOMAIN_PUBLIC` rather than through WireGuard means a notification doesn't depend on the phone's tunnel being up.

# Notes

1. There is no `server.yml`. Every setting is an environment variable, named `NTFY_` plus the option name from the ntfy docs uppercased with hyphens turned into underscores (`base-url` becomes `NTFY_BASE_URL`). This is deliberate: a config file would have to be seeded into appdata by a `hooks.py` before first start, whereas environment variables make `compose.yaml` and `secret.sops.env` the complete configuration, reproducible on a fresh host with nothing created by hand.

2. Accounts, permissions, and tokens are three separate lists, all declared as environment variables:

   ```
   NTFY_AUTH_USERS=<username>:<bcrypt-hash>:<role>,...
   NTFY_AUTH_ACCESS=<username>:<topic-pattern>:<permission>,...
   NTFY_AUTH_TOKENS=<username>:<token>[:<label>],...
   ```

   Entries are comma-separated. A token must start with `tk_` and be exactly 32 characters including that prefix. Tokens are not accounts — each one belongs to a user in `NTFY_AUTH_USERS` and carries that user's permissions, so a service account needs a row in both lists.

3. `<role>` is either `admin` or `user`. An admin has read-write on every topic and ignores `NTFY_AUTH_ACCESS` entirely, so writing ACL rules for one does nothing. A `user` starts with no permissions at all: `NTFY_AUTH_DEFAULT_ACCESS=deny-all` means anything without a matching ACL entry is refused, which is what makes the instance safe to put on a public hostname.

4. `<permission>` is `read-write` (`rw`), `read-only` (`ro`), `write-only` (`wo`), or `deny`. Read means subscribe, write means publish. `<topic-pattern>` is an exact name or a `*` wildcard (`frigate-*`); `*` is the only metacharacter. A `<username>` of `*` or `everyone` means unauthenticated requests, not all users — there should be no such entry unless anonymous access is wanted.

5. Service accounts get `wo` on their own topics and nothing else, so a compromised publisher can't read back alert history or post a fake all-clear into another service's topic:

   ```
   NTFY_AUTH_ACCESS=gatus:alerts:wo,frigate:frigate-*:wo
   ```

6. To add an account, generate a password hash and, for a service, a token:

   ```
   # Generate a hash
   docker run --rm -it binwiederhier/ntfy user hash
   # Generate a token
   head -c 256 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c 29
   ```

   **Prefix the random string with `tk_`**. `user hash` takes no username because it only turns a password into a bcrypt string; it writes nothing and never touches the server. The username is assigned by the entry you add to `NTFY_AUTH_USERS`. Append the new entries to the three lists in `secret.sops.env`, re-encrypt with `sops --encrypt --in-place`, and deploy. A service account's password is never used, so generate a random one and discard it.

7. These lists own the database. Users and tokens declared in the config are marked provisioned, and removing an entry deletes it from `user.db` at the next start. A password changed from the web UI doesn't survive a restart either. Rotate a credential by editing `secret.sops.env` and redeploying, not from the UI.

8. `NTFY_AUTH_USERS` must be single-quoted in `secret.sops.env`:

   ```
   NTFY_AUTH_USERS='admin:$2a$10$...:admin,gatus:$2a$10$...:user'
   ```

   A bcrypt hash contains `$`, and `.env` is not only the file `env_file:` reads. It's also the project env file compose interpolates against, so an unquoted `$Lo7Hscff...` is read as a variable name, warned about, and replaced with a blank string. Single-quoted values are used literally; the quotes are stripped before the container sees them, and `decrypt_secrets.py` keeps them because it splits on the first `=` only. `NTFY_AUTH_ACCESS` and `NTFY_AUTH_TOKENS` contain no `$` and don't need it. This is the same hazard as the Traefik dashboard's password hash, which dodged it by using `{SHA}` instead of bcrypt.

9. After a deploy, confirm with `docker compose --project-directory services/ntfy exec ntfy env | grep NTFY_AUTH` that each hash still reads `$2a$10$` followed by 53 characters. A hash that stops at `$2a$10$:` means interpolation ate it.

10. bcrypt is one-way, so the admin password can't be recovered from the config and belongs in a password manager. Tokens are the opposite: they're stored verbatim, so decrypting `secret.sops.env` always shows them. If the admin password is lost, generate a new hash, replace that one field, and redeploy.

11. `${MNT_APPDATA}/ntfy` must exist and be writable by `568` before the first deploy. ntfy creates `cache.db` and `user.db` itself, but Docker creates a missing bind mount source as `root`, which the container then can't write to, and it restart-loops.

12. `NTFY_BEHIND_PROXY=true` is required because every request arrives from Traefik. Without it, ntfy rate-limits by the proxy's IP and treats all visitors as one.

13. `NTFY_UPSTREAM_BASE_URL=https://ntfy.sh` exists only so iOS can get background notifications: the iOS app relies on ntfy.sh's APNs relay, which has to be able to reach this server. What's forwarded is a poll request carrying the message ID and the SHA256 of the topic URL — not the topic name and not the message, which the phone then fetches from here directly. If it can't reach this server, the notification still appears, but only as `New message`.
