# What it's for

Immich is a self-hosted photo and video library, similar to Google Photos.

[Check out the project](https://immich.app)

# Why it's needed

1. Photos and videos are backed up automatically from phones and stored on the NAS, without depending on a cloud storage plan.

2. Machine learning features like face recognition and smart search run locally. The ML container uses OpenVINO with the host's Intel GPU (`/dev/dri`).

# Known caveats

1. Immich releases often include breaking changes. Read the release notes before updating, especially across major versions.

2. The Postgres and Valkey images are pinned by digest, as in Immich's official compose file. Update them only when Immich's release notes say to.

3. The `-openvino` ML image only works on Intel hardware. Use a different tag (or none) on other hardware.
