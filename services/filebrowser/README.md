# What it's for

File Browser is a web-based file manager.

[Check out the project](https://filebrowser.org)

# Why it's needed

Files on the NAS (cloud storage, media, torrents, appdata, and the hardpoint) can be browsed, uploaded, downloaded, and moved from the browser, without SMB shares or SSH.

# Notes

1. All of appdata is mounted, which includes every service's config, Deploy Agent's decrypted `.env` files, and `age.key`. Any File Browser user with access to that mount can read every secret in the stack. Restrict that mount to admin users.

2. Files added to the Nextcloud data directory through File Browser bypass Nextcloud, so they won't show up in Nextcloud until it rescans (`occ files:scan`).

3. The container runs as UID/GID `568:568`, so it can only read and write what that user is allowed to.
