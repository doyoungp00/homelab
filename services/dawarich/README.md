# What it's for

Dawarich is a self-hosted location history tracker, similar to Google Maps Timeline.

[Check out the project](https://dawarich.app)

# Why it's needed

1. Location history is very personal data. Keeping it on the local server means it isn't stored or analysed by a third party.

2. Existing history (e.g. a Google Takeout export) can be imported, and phones can keep reporting new points through apps like OwnTracks or Overland.

# Notes

1. The app container is limited to 0.5 CPU and 4G of memory by default, with one web worker (`WEB_CONCURRENCY`) and three background job threads (`BACKGROUND_PROCESSING_CONCURRENCY`). This keeps idle usage low, but large imports will be slow. Raise these temporarily if needed.

2. Two-factor authentication requires the `OTP_ENCRYPTION_*` keys, which are not set.

3. The `postgis/postgis` image is x64 only. On ARM, use the commented-out `imresamu/postgis` image instead.
