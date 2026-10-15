"""Assemble Homepage's live config from the committed files plus a local overlay.

Everything under services/homepage/config/ and services/homepage/images/ is
public and version-controlled.
Anything that should exist only on this machine goes in a matching file under
${MNT_APPDATA}/homepage/local/, which is never committed; this appends it to
the public file and writes the result into the config/ directory Homepage
actually reads.

Appending works without parsing anything. services.yaml is a top-level list of
single-key groups, so one list's items follow another's, and CSS resolves
later rules last by cascade. That keeps comments and key order intact, which a
YAML round-trip would not.

Two rules for an overlay file:
  - no leading `---`, or it opens a second YAML document and Homepage reads
    only the first, silently dropping every public group;
  - add new groups rather than extending existing ones, since two
    `- Surveillance:` entries render as two separate groups.

Note this makes ${MNT_APPDATA}/homepage/config/ generated. Editing files there
no longer survives a deploy — edit the repo, or local/, instead.
"""

from __future__ import annotations

from pathlib import Path

CONFIG = "config"
IMAGES = "images"
LOCAL = "local"


def files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []


def pre_deploy(ctx):
    changed = False

    # Config: text, with a machine-local overlay appended when one exists.
    # |= rather than `or` throughout — `or` short-circuits, which would skip
    # the writes for every file after the first change.
    for src in files(ctx.service_dir / CONFIG):
        rel = src.relative_to(ctx.service_dir / CONFIG)
        text = src.read_text()
        overlay = ctx.appdata / LOCAL / rel
        if overlay.is_file():
            text = f"{text.rstrip(chr(10))}\n\n{overlay.read_text()}"
        changed |= ctx.write_if_changed(ctx.appdata / CONFIG / rel, text)

    # Backgrounds and icons, mounted at /app/public/images and referenced as
    # /images/<name> from settings.yaml. Copied byte-exact; appending an
    # overlay would only corrupt a JPEG, so private images instead just live
    # in appdata under a name the repo doesn't use — nothing here deletes, so
    # they survive untouched.
    for src in files(ctx.service_dir / IMAGES):
        changed |= ctx.sync(src.relative_to(ctx.service_dir).as_posix())

    return changed
