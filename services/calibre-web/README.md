# What it's for

Calibre-Web is a web app for browsing, reading, and managing an ebook library built with Calibre.

[Check out the project](https://github.com/janeczku/calibre-web)

# Why it's needed

1. The Calibre desktop app has to run on a machine with direct access to the library. Calibre-Web serves the same library over the browser, so books can be browsed, read, and downloaded from any device without installing anything.

2. With the `universal-calibre` Docker mod, Calibre's `ebook-convert` binary is included in the container. Books can be converted between formats (e.g. EPUB to KEPUB or MOBI) right from the web UI, and sent straight to e-readers.

# Notes

1. The `universal-calibre` mod is x64 only. On other architectures, remove `DOCKER_MODS` and conversion won't be available.

2. The mod downloads and installs Calibre's conversion tools on first boot, which takes a while. The healthcheck has a long `start_period` to account for this, so the container may show as `starting` for several minutes after the first deploy.

3. Calibre-Web doesn't create a library on its own. `PATH_BOOKS` must point to an existing Calibre library (a directory containing Calibre's `metadata.db`) before it can be selected in the initial setup.
