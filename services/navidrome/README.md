# What it's for

Navidrome is a music server for streaming a local music library.

[Check out the project](https://www.navidrome.org)

# Why it's needed

The local music library can be streamed from the browser or from any Subsonic-compatible app, at home and remotely through `DOMAIN_PUBLIC`.

# Notes

1. Navidrome is exposed publicly, so it's covered by CrowdSec. Use strong passwords for every user.

2. `hooks.py` installs the [nd-lyrics](https://github.com/J0R6IT0/navidrome-lyrics-plugin) plugin into `/data/plugins` before each deploy, which is how tracks with no lyrics of their own get them fetched on demand. The release is pinned, so upgrading means bumping both `VERSION` and `SHA256` in `hooks.py`. Get the new digest with:

   ```bash
   curl -fsSL https://github.com/J0R6IT0/navidrome-lyrics-plugin/releases/download/<tag>/nd-lyrics.ndp | sha256sum
   ```

   A mismatch fails the deploy rather than installing the file, so a release asset that changed under a tag is caught instead of being run.

3. The plugin has to be enabled once by hand, under **Settings → Plugins** in the web UI. The hook only puts the file in place; Navidrome won't grant a plugin its declared permissions until someone approves them. That approval and every plugin setting live in Navidrome's database under `${MNT_APPDATA}/navidrome/data`, not in this repo, so a fresh host gets the plugin from `hooks.py` but none of its configuration.

4. `ND_LYRICSPRIORITY` in `compose.yaml` is what actually wires the plugin in. It's Navidrome's default list with `nd-lyrics` appended last, so sidecar files and embedded tags keep winning. The entry has to match the plugin's filename without `.ndp`; drop the entry and the plugin loads but is never consulted.

5. The library is mounted read-write so the plugin can save what it fetches as `.lrc` files next to each song. That's off by default — turn on **Write lyrics to sidecar files** in the plugin's settings. Worth doing: `.lrc` sits ahead of `nd-lyrics` in note 4's list, so once a file exists the plugin is never asked for that track again, and the next scan folds the lyrics into the song record, which is the only way they appear in Navidrome's own web player. The web UI never asks plugins for anything.

6. Navidrome itself never writes to the library — it doesn't edit tags and has no delete — so that plugin is the only thing in here that can touch the music. It also asks for outbound HTTP to any host, since the lyrics providers are configurable. Navidrome is public (note 1), so keep **Overwrite existing lyrics files** off, and consider turning on **Write lyrics to a custom path**, which confines every sidecar to one folder under the library root instead of scattering them through it.

7. Navidrome keeps its own accounts, on purpose, rather than logging in through Authentik. It has no OIDC, only a trusted username header (`ND_EXTAUTH_*`), and doing that safely here would take a fixed Traefik IP (the header can't be trusted from the whole `proxy` network), a Navidrome-only login wall that admits `family`, open `/rest` and `/share` routes that strip any client-sent username header, and still a Navidrome password per person for music apps, which use Subsonic's own login. That buys single sign-on for the web player only. See [Navidrome's authentication docs](https://www.navidrome.org/docs/usage/integration/authentication/) if that trade-off changes.
