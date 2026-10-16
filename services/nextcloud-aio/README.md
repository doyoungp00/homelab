# What it's for

Nextcloud is a self-hosted cloud storage and collaboration platform. Nextcloud All-in-One (AIO) is its official Docker installation, which manages Nextcloud and its supporting services for you.

[Check out the project](https://github.com/nextcloud/all-in-one)

# Why it's needed

Files, contacts, and calendars sync across devices and can be shared with others, while staying on the NAS instead of a third-party cloud.

# Known caveats

1. Only the mastercontainer is defined in `compose.yaml`. It creates every other container (Apache, database, Redis, etc.) itself, so those aren't managed by this repo or Deploy Agent. Updates and backups are done through the AIO interface.

2. The AIO interface is on port `8080` of the host, with a self-signed certificate. The Nextcloud web UI is served by the dynamically created `nextcloud-aio-apache` container, which joins the `proxy` network through `APACHE_ADDITIONAL_NETWORK`.

3. `NEXTCLOUD_DATADIR` must not be changed after the initial installation.

4. WebDAV sync needs encoded slashes and other characters allowed. This is set globally on Traefik's `websecure` entrypoint, since there is no per-router option.
