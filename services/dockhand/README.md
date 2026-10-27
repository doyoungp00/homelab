# What it's for

Dockhand is a web UI for managing Docker containers, images, and compose stacks.

[Check out the project](https://github.com/Finsys/dockhand)

# Why it's needed

It gives an overview of every container on the host in one place, and shows when newer images are available for services that use a plain `image:` tag.

# Notes

1. Dockhand has read-write access to the Docker socket, which is effectively root on the host. It sits behind the Authentik login wall, and its own login uses OIDC against the `dockhand` application in Authentik (`authentik/blueprints/dockhand.yaml`), which only the `admins` group can use. The OIDC settings on Dockhand's side live in its database, not this repo. Keep the local admin account as a way back in if Authentik is down.

2. Deployments are owned by Deploy Agent and this repo. Changes made to a stack through Dockhand will be reverted the next time that service is deployed. Make permanent changes in the repo instead.
