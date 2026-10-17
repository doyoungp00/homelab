# What it's for

code-server runs VS Code on the server and serves it through the browser.

[Check out the project](https://github.com/coder/code-server)

# Why it's needed

1. A full development environment is available from any device with a browser, without setting up tools locally. The home directory is persisted, so projects, extensions, and settings survive container rebuilds.

2. The custom image includes the tools needed to work on this homelab and other projects: Git, GitHub CLI, Python, .NET SDK (LTS), Rust, and sops for editing the `secret.sops.env` files.

# Notes

1. The toolchains are installed in the image, outside of `/home/coder`, so they don't bloat the persisted home directory. Updating them means rebuilding the image (`docker compose build --pull`). Anything installed by hand outside of `/home/coder` is lost on rebuild.

2. The sops binary is downloaded for `amd64` only. On other architectures, change the download URL in the `Dockerfile`.

3. The container runs as UID/GID `568:568`, so files created in the editor are owned by that user on the host.
