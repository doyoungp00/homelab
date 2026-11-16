# Wiki schema

This vault is a personal wiki that you, the agent, maintain. I add sources and
ask questions; you do the reading, summarizing, cross-linking, filing, and
upkeep. I read the result in Obsidian. Change this file only when we agree a
convention should change.

## Layout

- `raw/` — sources I've added: clipped articles, papers, notes, transcripts,
  images. **Never edit, rename, or delete anything here.** It's the record the
  wiki is built from.
- `wiki/` — pages you write and keep current. One topic per page.
  - `wiki/sources/` — one summary page per source in `raw/`.
  - `wiki/entities/` — people, organizations, places, products.
  - `wiki/concepts/` — ideas, methods, recurring themes.
  - `wiki/answers/` — answers worth keeping, filed from our conversations.
- `index.md` — the catalogue: every wiki page, by category, with a link and a
  one-line summary. Read it first; keep it complete.
- `log.md` — append-only record of everything you do here. Never rewrite past
  entries.

## Page conventions

- File names are lowercase-with-dashes, e.g. `wiki/concepts/spaced-repetition.md`.
- Start every page with frontmatter:

  ```yaml
  ---
  type: source | entity | concept | answer
  sources: [raw/2026-11-16-some-article.md]
  updated: 2026-11-16
  ---
  ```

- Link related pages with Obsidian wikilinks, `[[spaced-repetition]]`, by file
  name without the folder. Link generously; that's what makes the wiki useful.
- Cite claims back to their source page or raw file. Mark anything you're
  unsure of, and anything that contradicts another page, rather than
  smoothing it over.
- Keep images and attachments next to the raw source that brought them, and
  embed them with `![[file.png]]`.

## Workflows

### Ingest (when I add something to `raw/`, or ask you to)

1. Read the source in full. Tell me the key takeaways and anything surprising
   or contradicting what the wiki already says, before writing.
2. Write its summary page in `wiki/sources/`.
3. Update every entity and concept page it touches, creating missing ones.
   One source often touches many pages; that's expected.
4. Update `index.md`.
5. Append to `log.md`.

Ingest one source at a time unless I say otherwise.

### Query (when I ask a question)

1. Read `index.md`, then the relevant pages. Search GBrain for anything the
   index doesn't lead you to.
2. Answer with links to the pages you used.
3. If the answer is worth keeping, offer to file it in `wiki/answers/`.

### Lint (when I ask, or on a schedule)

Check for contradictions between pages, claims that newer sources have made
stale, orphan pages nothing links to, concepts mentioned often but missing a
page, missing cross-links, and gaps a web search could fill. Report what you
found, fix what's clearly fixable, and ask about the rest. Log it.

## log.md format

One line per action, newest last, so it stays easy to grep:

```
2026-11-16 ingest  raw/2026-11-16-some-article.md -> 6 pages updated
2026-11-16 query   "how does X compare to Y" -> filed wiki/answers/x-vs-y.md
2026-11-16 lint    2 contradictions flagged, 3 orphans linked
```

## Syncing

The vault syncs to my devices through Syncthing. If you find a file named like
`page.sync-conflict-20261116-123456-ABCDEFG.md`, we both edited the same page:
merge the two versions into the original, delete the conflict copy, and log
it.
