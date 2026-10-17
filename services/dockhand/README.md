# What it's for

Dockhand is a web UI for managing Docker containers, images, and compose stacks.

[Check out the project](https://github.com/Finsys/dockhand)

# Why it's needed

It gives an overview of every container on the host in one place, and shows when newer images are available for services that use a plain `image:` tag.

# Notes

1. Dockhand has read-write access to the Docker socket, which is effectively root on the host. Make sure authentication is enabled.

2. Deployments are owned by Deploy Agent and this repo. Changes made to a stack through Dockhand will be reverted the next time that service is deployed. Make permanent changes in the repo instead.
