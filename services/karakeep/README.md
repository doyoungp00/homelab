# What it's for

Karakeep is a bookmarking app for links, notes, and images, with full-text search and page archiving.

[Check out the project](https://karakeep.app)

# Why it's needed

1. Saved pages are archived locally (screenshots, PDF, full page, and video), so they stay readable even if the original page changes or goes offline.

2. Bookmarks are searchable through Meilisearch, and can be tagged automatically by AI if `OPENAI_API_KEY` is set.

# Notes

1. Full page archives, PDFs, and video downloads are all enabled, which can use a lot of disk space over time.

2. Meilisearch is pinned to a specific version. Upgrading it across versions may require a dump and re-import of the index.

3. The headless Chrome container (port 9222) has no authentication and is reachable by any container on the `proxy` network.
