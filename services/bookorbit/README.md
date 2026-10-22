# What it's for

BookOrbit is a self-hosted library for ebooks and audiobooks, with reading progress, metadata management, and optional text-to-speech.

[Check out the project](https://github.com/bookorbit/bookorbit)

# Why it's needed

Books on the NAS can be browsed, read, and downloaded from any device through the browser, without installing anything.

# Notes

1. `SETUP_BOOTSTRAP_TOKEN` is asked for when creating the first admin account. It's only needed once.

2. `PATH_BOOKS` must be readable and writable by `PUID:PGID`. BookOrbit only fixes ownership of its own `/data` directory, not the books folder, and needs write access for uploads and metadata write-back.

3. The app and PostgreSQL data must be on a local filesystem, not a network mount.

4. The Kokoro text-to-speech container is opt-in and doesn't start by default. Run with `--profile tts` to enable it.
