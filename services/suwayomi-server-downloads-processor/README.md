# What it's for

A custom service that moves manga downloaded by Suwayomi-Server (in the Arr Stack) into Suwayomi's local source library.

It watches the download folder and rearranges each title into the local source layout:

```
<download>/<Title>/<pages> + info.txt
  becomes
<archive>/<Title>/Chapter/<pages> + info.txt
<archive>/<Title>/details.json
```

# Why it's needed

Downloaded chapters are tied to the online source they came from. Moving them into the local source keeps them in the library permanently, even if the original source changes or goes away.

# Known caveats

1. A folder is only moved once its contents have stopped changing for 30 seconds (`--settle-seconds`), so it doesn't grab a download that's still in progress.

2. If a title already exists in the archive, the new one is saved as `<Title> (1)`, `<Title> (2)`, and so on, rather than merged into the existing folder.

3. Processed folders are recorded in a SQLite database in appdata, so a folder is never processed twice.

4. It has no web UI or health endpoint. Check its logs in Dozzle.
