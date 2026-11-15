# What it's for

MeTube is a web UI for [yt-dlp](https://github.com/yt-dlp/yt-dlp): paste a video link from almost any site, pick a quality or format, and it downloads to the NAS.

[Check out the project](https://github.com/alexta69/metube)

# Why it's needed

Videos from sites without a download button can be saved from any device through the browser. yt-dlp supports far more video sites than JDownloader's plugins, and is fixed faster when a site changes.

# Notes

1. Downloads go to `${MNT_MEDIA}/Videos`. Add it as a library in Jellyfin to watch them there. The queue and history are kept in `${MNT_APPDATA}/metube/state`.

2. MeTube has no login, so it's behind the Authentik login wall (admins only). The browser extension and bookmarklet work from a browser that's already logged in.

3. On every start, MeTube takes ownership of `/downloads` recursively (`PUID:PGID`), so don't point it at a folder other services own.

4. Downloads go direct by default, since many video sites block VPN addresses. To send one through the VPN, pick the **VPN** preset under Advanced Options when adding it. That routes it through `firefox-gluetun`'s HTTP proxy (see the Firefox README), so the Firefox stack must be running, and the download fails instead of using the home IP when the tunnel is down.

5. Download failures are almost always an outdated yt-dlp. A new image is published for every yt-dlp release, so redeploying usually fixes them. Sites that need a login take a cookies file, uploaded in the UI.

6. SSRF protection is on (`ALLOW_PRIVATE_ADDRESSES` unset), so a pasted URL can't make it fetch services on the LAN.
