# What it's for

Homepage is a dashboard with links and live widgets for every service in the stack.

[Check out the project](https://gethomepage.dev)

# Why it's needed

1. It's a single starting page for the homelab, with status and stats from each service.

2. Services are discovered from `homepage.*` labels on each container, so adding a service to the dashboard is done in that service's `compose.yaml`.

# Known caveats

1. `${MNT_APPDATA}/homepage/config` is generated. `hooks.py` builds it on every deploy from `config/` in this repo, plus a machine-local overlay in `${MNT_APPDATA}/homepage/local/`. Editing files in `config/` in appdata won't survive a deploy. Edit the repo copy or the overlay instead.

2. Overlay files are appended to the matching repo file. They must not start with `---`, and should add new groups rather than extend existing ones. See the docstring in `hooks.py`.

3. `{{HOMEPAGE_VAR_*}}` values must be declared in `compose.yaml`'s `environment`. Substitution silently stops working if they come from a mounted `.env` file.
