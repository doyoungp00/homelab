# What it's for

Chrony is a local NTP server that mirrors Cloudflare Time Services.

[Check out the project](https://github.com/dockur/chrony)

# Why it's needed

Some devices that are deliberately disconnected from the internet (IP cameras, IoT devices, etc.) may experience clock drift over prolonged periods of time. A local NTP server allows devices to sync time while still disconnected.

# Known caveats

1. If a device has a fixed NTP server (`pool.ntp.org`, `time.windows.com`) with no option to change this setting, use AdGuard Home's DNS rewrite feature. Or, modify AdGuard Home's config to add DHCP option 42 (network must be using AdGuard Home as the DHCP server).

2. If chrony itself is not connected to the internet, it cannot reach the upstream source and will refuse any requests.\
   Modify chrony's configs to use its own clock as the source.
