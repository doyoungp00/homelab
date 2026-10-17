# What it's for

Navidrome is a music server for streaming a local music library.

[Check out the project](https://www.navidrome.org)

# Why it's needed

The local music library can be streamed from the browser or from any Subsonic-compatible app, at home and remotely through `DOMAIN_PUBLIC`.

# Notes

1. The music folder is mounted read-only, so Navidrome can't edit tags or delete files. Manage the library from outside Navidrome.

2. Navidrome is exposed publicly, so it's covered by CrowdSec. Use strong passwords for every user.
