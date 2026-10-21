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

3. The plugin has to be enabled once by hand, under **Settings → Plugins** in the web UI. The hook only puts the file in place; Navidrome won't grant a plugin its declared permissions until someone approves them.

4. `ND_LYRICSPRIORITY` in `compose.yaml` is what actually wires the plugin in. It's Navidrome's default list with `nd-lyrics` appended last, so sidecar files and embedded tags keep winning. The entry has to match the plugin's filename without `.ndp`; drop the entry and the plugin loads but is never consulted.
