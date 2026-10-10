#!/usr/bin/env python3
"""
process_downloads.py

Watches a download folder for newly-arrived manga folders and moves them
into an archive folder in the target layout:

    <download_dir>/<Title>/<pages>.webp + info.txt
        becomes
    <archive_dir>/<Title>/Chapter/<pages>.webp + info.txt
    <archive_dir>/<Title>/details.json      (next to Chapter, not inside it)

Detection is both:
  - event-based: a watchdog observer reacts to new folders appearing in
    the download directory (if the `watchdog` package is installed).
  - periodic: a poll loop lists the download directory on an interval,
    which also catches anything the watcher missed (e.g. folders copied
    in before the service started, or a missed inotify event).

Both paths funnel into the same process_candidate() function, which is
guarded so a folder is only ever processed once even if both triggers
fire for it.

Copy-in-progress safety: a folder is only moved once its *contents* have
stopped changing. Rather than trusting file mtimes (many copy tools, e.g.
rsync -a, preserve the source's original mtimes, so a file can already
look "old" while it's still mid-copy), stability is judged by comparing a
fingerprint (total byte size + file count) of the folder across repeated
checks. Only once the fingerprint has been unchanged for --settle-seconds
is a folder considered done copying. The event watcher self-reschedules a
follow-up check every --settle-seconds until a folder is either stable or
gone, so it doesn't have to wait on the (potentially much longer) poll
--interval to notice.

Archive naming: if <archive_dir>/<Title> already exists, the incoming
folder is archived as "<Title> (1)", "<Title> (2)", etc. -- the first free
suffix -- rather than overwriting or skipping.

Usage (persistent service, recommended):
    python process_downloads.py --download /data/download --archive /data/archive

Usage (single pass, e.g. from cron/Portainer's own scheduler instead):
    python process_downloads.py --download /data/download --archive /data/archive --once
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# --- Field mapping (info.txt -> details.json) -------------------------

FIELD_MAP = {
    "갤러리 넘버": "gallery_number",
    "제목": "title",
    "작가": "author",
    "그룹": "group",
    "타입": "type",
    "시리즈": "series",
    "캐릭터": "character",
    "태그": "tags",
    "언어": "language",
}

NA_VALUES = {"n/a", "na", ""}
STATUS_VALUES = ["0 = Unknown", "1 = Ongoing", "2 = Completed", "3 = Licensed"]

IGNORED_SOURCE_FILES = {"details.json"}  # info.txt is kept -- see below


def split_values(raw: str):
    return [v.strip() for v in raw.split(",") if v.strip()]


def is_na(raw: str) -> bool:
    return raw.strip().lower() in NA_VALUES


def parse_info_txt(text: str) -> dict:
    """Parse info.txt content (already read as a string) into field dict."""
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key_kr, _, value = line.partition(":")
        key = FIELD_MAP.get(key_kr.strip())
        if key is None:
            continue
        fields[key] = value.strip()
    return fields


def build_details(fields: dict, raw_info_text: str = "") -> dict:
    details = {
        "title": "",
        "author": "",
        "artist": "",
        "description": "",
        "genre": [],
        "status": "2",
        "_status values": STATUS_VALUES,
    }
    genre = []

    title = fields.get("title", "")
    if title and not is_na(title):
        details["title"] = title

    author = fields.get("author", "")
    if author and not is_na(author):
        details["author"] = author
        for v in split_values(author):
            genre.append(f"artist:{v}")

    group = fields.get("group", "")
    if group and not is_na(group):
        details["artist"] = group
        for v in split_values(group):
            genre.append(f"group:{v}")

    type_ = fields.get("type", "")
    if type_ and not is_na(type_):
        for v in split_values(type_):
            genre.append(f"type:{v}")

    series = fields.get("series", "")
    if series and not is_na(series):
        for v in split_values(series):
            genre.append(f"series:{v}")

    character = fields.get("character", "")
    if character and not is_na(character):
        for v in split_values(character):
            genre.append(f"character:{v}")

    tags = fields.get("tags", "")
    if tags and not is_na(tags):
        genre.extend(split_values(tags))

    language = fields.get("language", "")
    if language and not is_na(language):
        for v in split_values(language):
            genre.append(f"language:{v}")

    details["genre"] = genre

    # Keep a full copy of info.txt in description, verbatim. json.dump()
    # automatically encodes embedded newlines as the two-character escape
    # \n in the written file, which is the standard/correct way to store
    # a multi-line string in a JSON string value.
    if raw_info_text:
        details["description"] = raw_info_text.strip("\n")

    return details


# --- SQLite audit log --------------------------------------------------
# Not used for skip/dedup logic (a folder disappears from the download
# dir once it's moved, so there's nothing left to re-skip) -- this is
# just a history/audit trail of what happened and when.


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_manga (
            title TEXT NOT NULL,
            archive_path TEXT NOT NULL,
            outcome TEXT NOT NULL,
            processed_at TEXT NOT NULL
        )
        """)
    conn.commit()
    return conn


def log_outcome(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    title: str,
    archive_path: str,
    outcome: str,
) -> None:
    """
    Best-effort audit logging. Deliberately never raises: a failure to
    write the audit log (e.g. permission issue on the db file) must not
    crash the service or get mistaken for the archive operation itself
    having failed -- by the time this is called for a "moved" outcome,
    the actual move already succeeded.
    """
    try:
        with lock:
            conn.execute(
                "INSERT INTO processed_manga (title, archive_path, outcome, processed_at) "
                "VALUES (?, ?, ?, ?)",
                (title, archive_path, outcome, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except sqlite3.Error:
        log.exception(
            "Could not write audit log entry for '%s' (outcome=%s) -- "
            "check permissions on the sqlite db file/directory",
            title,
            outcome,
        )


# --- Naming ----------------------------------------------------------


def unique_target_dir(archive_dir: str, title: str) -> str:
    """<archive_dir>/<title>, or the first free '<title> (n)' if taken."""
    candidate = os.path.join(archive_dir, title)
    if not os.path.exists(candidate):
        return candidate
    n = 1
    while True:
        candidate = os.path.join(archive_dir, f"{title} ({n})")
        if not os.path.exists(candidate):
            return candidate
        n += 1


# --- Core processing -------------------------------------------------------


class Processor:
    def __init__(
        self,
        download_dir: str,
        archive_dir: str,
        db_conn,
        db_lock,
        settle_seconds: float,
    ):
        self.download_dir = download_dir
        self.archive_dir = archive_dir
        self.db_conn = db_conn
        self.db_lock = db_lock
        self.settle_seconds = settle_seconds

        self._in_progress = set()
        self._in_progress_lock = threading.Lock()

        # path -> ((total_size, file_count), first_seen_unchanged_at)
        self._fingerprints = {}
        self._fp_lock = threading.Lock()

    def candidate_dirs(self):
        """Top-level directories currently sitting in the download folder."""
        try:
            with os.scandir(self.download_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        yield entry.path
        except FileNotFoundError:
            return

    @staticmethod
    def _fingerprint(path: str):
        total_size = 0
        count = 0
        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                try:
                    st = os.stat(os.path.join(dirpath, name))
                except OSError:
                    continue
                total_size += st.st_size
                count += 1
        return (total_size, count)

    def _is_stable(self, path: str) -> bool:
        """
        True once this folder's fingerprint has been unchanged for at
        least settle_seconds across repeated calls to this method.
        Must be called more than once, spaced out over time, to ever
        return True -- a single call always primes the baseline.
        """
        fp = self._fingerprint(path)
        now = time.time()
        with self._fp_lock:
            prev = self._fingerprints.get(path)
            if prev is None or prev[0] != fp:
                self._fingerprints[path] = (fp, now)
                return False
            _, first_seen = prev
            return (now - first_seen) >= self.settle_seconds

    def _forget(self, path: str) -> None:
        with self._fp_lock:
            self._fingerprints.pop(path, None)

    def try_process(self, path: str) -> bool:
        """
        Entry point for both the watcher and the poll loop.
        Returns True if the folder is done being dealt with (moved, or a
        terminal error/skip) -- i.e. no need to keep retrying it. Returns
        False if it's still waiting on something (usually: still copying,
        or no info.txt/details.json yet).
        """
        with self._in_progress_lock:
            if path in self._in_progress:
                return False
            self._in_progress.add(path)
        try:
            return self._process(path)
        finally:
            with self._in_progress_lock:
                self._in_progress.discard(path)

    def _process(self, path: str) -> bool:
        if not os.path.isdir(path):
            self._forget(path)
            return True  # already moved / gone, nothing left to do

        title = os.path.basename(path.rstrip(os.sep))

        if not self._is_stable(path):
            log.debug("Still copying (or just arrived), will recheck: %s", title)
            return False

        details_src = os.path.join(path, "details.json")
        info_src = os.path.join(path, "info.txt")

        if os.path.isfile(details_src):
            try:
                with open(details_src, "r", encoding="utf-8") as f:
                    details = json.load(f)
            except Exception:
                log.exception("Failed to read existing details.json for %s", title)
                self._forget(path)
                return True  # terminal for this attempt; won't fix itself on retry
        elif os.path.isfile(info_src):
            try:
                with open(info_src, "r", encoding="utf-8") as f:
                    raw_info_text = f.read()
                details = build_details(parse_info_txt(raw_info_text), raw_info_text)
            except Exception:
                log.exception("Failed to parse info.txt for %s", title)
                self._forget(path)
                return True
        else:
            log.debug("No details.json or info.txt yet, skipping for now: %s", title)
            return False  # keep waiting -- info.txt may still land

        target_dir = unique_target_dir(self.archive_dir, title)
        if target_dir != os.path.join(self.archive_dir, title):
            log.info(
                "'%s' already exists in archive, using '%s' instead",
                title,
                os.path.basename(target_dir),
            )

        tmp_dir = target_dir + ".processing"
        chapter_dir = os.path.join(tmp_dir, "Chapter")

        try:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(chapter_dir)

            for entry in os.listdir(path):
                if entry in IGNORED_SOURCE_FILES:
                    continue
                # copy_function=copyfile (instead of the shutil.move default,
                # copy2) skips copying permission bits/metadata after the
                # file content copy. copy2's metadata step (copystat/chmod)
                # can raise PermissionError on some destination filesystems
                # (notably NFS/CIFS/SMB mounts, or non-root users without
                # chmod rights) even when the content copy itself is fine --
                # this matters here because download/archive are commonly
                # separate mounts, which forces shutil.move onto the
                # copy+delete fallback path instead of a plain os.rename.
                shutil.move(
                    os.path.join(path, entry),
                    os.path.join(chapter_dir, entry),
                    copy_function=shutil.copyfile,
                )

            with open(
                os.path.join(tmp_dir, "details.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(details, f, ensure_ascii=False, indent=4)

            # Guard against a last-second collision (e.g. two folders with
            # the same title settling around the same time).
            final_dir = target_dir
            while True:
                try:
                    os.rename(tmp_dir, final_dir)
                    break
                except FileExistsError:
                    final_dir = unique_target_dir(self.archive_dir, title)

            shutil.rmtree(
                path, ignore_errors=True
            )  # drop the now-empty (or details.json-only) source dir
            self._forget(path)

            log.info("Archived: %s -> %s", title, final_dir)
            log_outcome(self.db_conn, self.db_lock, title, final_dir, "moved")
            return True
        except Exception:
            log.exception("Failed to archive %s", title)
            log_outcome(self.db_conn, self.db_lock, title, target_dir, "error")
            self._forget(path)
            return True


# --- Watchdog (event-based) wiring, optional --------------------------


def build_observer(processor: Processor, download_dir: str, settle_seconds: float):
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        log.warning(
            "`watchdog` package not installed; running in poll-only mode. "
            "Install with `pip install watchdog` to enable event-based detection."
        )
        return None

    def check_and_maybe_reschedule(path: str):
        if not os.path.isdir(path):
            return  # gone (processed, or removed by hand)
        handled = processor.try_process(path)
        if not handled:
            # Still copying, or still waiting on info.txt -- check again
            # rather than waiting for the next (possibly much longer) poll.
            threading.Timer(
                settle_seconds, check_and_maybe_reschedule, args=[path]
            ).start()

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                return
            if os.path.dirname(event.src_path.rstrip(os.sep)) != download_dir.rstrip(
                os.sep
            ):
                return
            threading.Timer(
                settle_seconds, check_and_maybe_reschedule, args=[event.src_path]
            ).start()

    observer = Observer()
    observer.schedule(Handler(), download_dir, recursive=False)
    return observer


# --- Main -------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", required=True, help="Download/inbox directory")
    parser.add_argument("--archive", required=True, help="Archive directory")
    parser.add_argument(
        "--db", default="processed_manga.db", help="Path to SQLite audit log"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Poll interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=30.0,
        help="How long a folder's contents must be unchanged before it's "
        "considered done copying (default: 30)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll pass over the download directory and exit "
        "(for use with an external scheduler like cron instead of running as a service). "
        "Note: folders still mid-copy will simply be skipped this pass and picked up "
        "on the next invocation.",
    )
    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Disable the event-based watcher even if `watchdog` is installed; poll only.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.download):
        log.error("Download directory does not exist: %s", args.download)
        sys.exit(1)
    os.makedirs(args.archive, exist_ok=True)

    db_conn = init_db(args.db)
    db_lock = threading.Lock()
    processor = Processor(
        args.download, args.archive, db_conn, db_lock, args.settle_seconds
    )

    if args.once:
        for path in list(processor.candidate_dirs()):
            processor.try_process(path)
        db_conn.close()
        return

    observer = (
        None
        if args.no_watch
        else build_observer(processor, args.download, args.settle_seconds)
    )
    if observer:
        observer.start()
        log.info("Event-based watcher active on %s", args.download)

    log.info("Polling %s every %.0fs", args.download, args.interval)
    try:
        while True:
            for path in list(processor.candidate_dirs()):
                processor.try_process(path)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if observer:
            observer.stop()
            observer.join()
        db_conn.close()


if __name__ == "__main__":
    main()
