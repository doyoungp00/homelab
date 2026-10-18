# What it's for

Speedtest Tracker runs Ookla speed tests on a schedule and keeps every result, charting download, upload, and latency over time.

[Check out the project](https://github.com/alexjustesen/speedtest-tracker)

# Why it's needed

It shows whether the ISP is delivering the speed being paid for, and makes a slow connection easier to tell apart from a problem inside the network. Note that this is only a way to keep a pulse on the connection. ISPs will **not** accept a claim based on these results, since they require results carried out using their own tool under their own conditions.

# Notes

1. `APP_KEY` is Laravel's encryption key, and must be `base64:` followed by 32 random bytes — `echo "base64:$(openssl rand -base64 32)"`. It isn't a password to be rotated on a schedule: changing it on an existing install makes everything already stored unreadable.

2. `APP_URL` has to match the address the UI is actually opened at, `https://` included, because Laravel builds absolute links and session cookies from it. A mismatch gives a page that loads but can't log in.

3. `ADMIN_NAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` only seed the first account, at the moment the database is created. Changing them later does nothing. Change the password from the UI instead.

4. Results are kept in a SQLite database under `${MNT_APPDATA}/speedtest-tracker/config`. The history survives a redeploy, but it lives only on the NAS and isn't reproduced from this repo.
