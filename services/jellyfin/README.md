# What it's for

Jellyfin is a media server for streaming movies and TV shows.

[Check out the project](https://jellyfin.org)

# Why it's needed

1. Media managed by the Arr Stack can be streamed to phones, TVs, and browsers, both at home and remotely through `DOMAIN_PUBLIC`.

2. Hardware transcoding through the host's GPU (`/dev/dri`) lets lower-powered clients play formats they don't support natively.

# Known caveats

1. The `render` (`107`) and `video` (`44`) group IDs in `group_add` are specific to this host. Check them with `getent group render video` on a new host, or hardware transcoding will fail.

2. Only `Movies` and `TV Series` are mounted. Other libraries need their own volume.

3. Jellyfin is exposed publicly, so it's covered by CrowdSec. Use strong passwords for every user.
