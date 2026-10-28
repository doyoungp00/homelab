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

4. Login is through OIDC against the `dawarich` application in Authentik (`authentik/blueprints/dawarich.yaml`), open to the `admins` and `family` groups. Both sides are in this repo: Dawarich reads its OIDC settings from `OIDC_*` variables on `dawarich_app`. `DAWARICH_OIDC_CLIENT_ID` and `DAWARICH_OIDC_CLIENT_SECRET` have to be set to the same values in both `dawarich/secret.sops.env` and `authentik/secret.sops.env`.

5. Dawarich never links an OIDC login to an existing account by email alone. When the emails match, it asks for that account's Dawarich password once, then links it. People without an account get a new one (`OIDC_AUTO_REGISTER`). It also rejects unverified emails, so the provider uses the shared "verified" email mapping in `authentik/blueprints/scope-mappings.yaml`. `OIDC_REDIRECT_URI` is set explicitly, since Dawarich would otherwise build it from `APPLICATION_URL`, which defaults to `http://localhost:3000`.

6. Dawarich isn't behind the login wall: phone apps such as OwnTracks and Overland post location points to its API with an API key.
