# bin/ — magento-wiki automation scripts

Scripts that fetch external sources (Hyvä, Magento, security, adjacent stack)
on a cron schedule and stage markdown drafts under
`../raw/shared/weekly-updates/<YYYY-Wnn>/`.

## Zero-cost design

Nothing in this folder calls the Claude / Anthropic API. Everything is pure
Python standard library + curl-grade HTTP. No API keys, no accounts, no
dollar cost. The LLM-based synthesis happens **only** during the interactive
Friday weekly review (your normal Claude Code usage, no extra charges).

## Files

| File | Purpose |
|------|---------|
| `fetch-sources.py` | The fetcher. Handles RSS, Atom, GitHub releases API, NVD CVE API, HTML diffs. |
| `sources.json` | Source list, grouped by category (`hyva`, `magento`, `security`, `adjacent`). |
| `weekly-hyva.sh` | Cron entry: Monday 07:00 — fetches Hyvä category. |
| `twice-weekly-magento.sh` | Cron entry: Tue+Fri 07:00 — fetches Magento + security. |
| `monthly-adjacent.sh` | Cron entry: 1st of month 07:00 — adjacent stack. |
| `run-all.sh` | Manual run of every category. For testing or ad-hoc refresh. |
| `weekly-review-prompt.md` | The prompt you paste into Claude on Friday afternoons. |
| `.fetch-state.json` | Internal state (last-seen items per source). **Do not hand-edit.** Auto-created on first run. |
| `logs/` | One log file per run. Safe to delete anything older than a week. |

## First-time setup

1. **Dry-run the fetcher** to verify `sources.json` parses and the script runs:

   ```bash
   cd ~/Documents/magento-wiki
   python3 bin/fetch-sources.py --category all --dry-run
   ```

   Expected: lines like `[hyva] DRY RUN: N new items across M sources, K errors`.
   Errors listed are likely URLs that need fixing in `sources.json` — see below.

2. **Fix any broken URLs in `sources.json`.** Sources I marked `VERIFY` in the
   notes use my best guess — check them against the real site and replace as
   needed. A fetch error just means that source is skipped; the rest still
   work. You can remove sources you don't care about.

3. **Do one real run** to populate the current week's folder and exercise state:

   ```bash
   bash bin/run-all.sh
   ```

   Check `../raw/shared/weekly-updates/<current-week>/` for draft files.

4. **Install the cron** with `crontab -e` and add these lines (replace
   `/home/user` with your actual home if different):

   ```cron
   # magento-wiki weekly update fetchers — zero-cost, stdlib only
   30 11 * * MON  /home/user/Documents/magento-wiki/bin/weekly-hyva.sh
   30 11 * * TUE  /home/user/Documents/magento-wiki/bin/twice-weekly-magento.sh
   30 11 * * FRI  /home/user/Documents/magento-wiki/bin/twice-weekly-magento.sh
   30 11 1 * *    /home/user/Documents/magento-wiki/bin/monthly-adjacent.sh
   ```

   Check with `crontab -l`. Times are **11:30** — machine is typically on
   after 11am, this gives a 30-minute buffer.

5. **If your machine is usually off at 11:30**, install `anacron`
   (`sudo apt install anacron`) so missed jobs run when the machine wakes up.
   Cron alone silently skips missed jobs.

## Adding a source

Edit `sources.json` and add an entry under the appropriate category. Supported
types:

### `rss` or `atom`

```json
{
  "name": "unique-slug",
  "type": "rss",
  "url": "https://example.com/feed.xml",
  "note": "Short description"
}
```

### `github-releases`

Uses the unauthenticated GitHub API (60 requests/hour — way more than we need).

```json
{
  "name": "unique-slug",
  "type": "github-releases",
  "repo": "owner/repo",
  "note": "Short description"
}
```

### `nvd-cve`

Queries the free NVD CVE API for keywords, last 14 days.

```json
{
  "name": "unique-slug",
  "type": "nvd-cve",
  "keywords": ["keyword1", "keyword2"],
  "note": "Short description"
}
```

### `html`

Best-effort "page changed" detector. Hashes the page body and flags when the
hash changes, staging the raw HTML under
`../raw/shared/weekly-updates/<week>/raw-html/<name>.html` for manual diffing
during the Friday review.

```json
{
  "name": "unique-slug",
  "type": "html",
  "url": "https://example.com/changelog.html",
  "note": "Short description"
}
```

## Removing a source

Just delete the entry from `sources.json`. The script won't touch it anymore;
its state stays in `.fetch-state.json` but is inert. You can prune
`.fetch-state.json` by hand or delete it entirely — on next run it gets
rebuilt, which means "everything looks new" for one run. Not a problem.

## Debugging

### "No new items ever"

The handlers filter against `.fetch-state.json`. If you're re-running after a
successful fetch, all items are already in the state and will be filtered as
seen. Either wait for actual new items, or:

```bash
rm bin/.fetch-state.json
bash bin/run-all.sh
```

### "Source X always errors"

Read `bin/logs/<category>-<date>.log` to see the exact error. Usually:
- URL is wrong → fix `sources.json`
- GitHub repo name is wrong → fix `sources.json`
- Site rate-limited / returned 403 → add a delay or drop the source
- Feed is malformed → some sites return RSS-looking garbage; drop or use `html` type instead

### "I want to test without waiting for Monday"

```bash
bash bin/weekly-hyva.sh
tail -50 bin/logs/hyva-$(date +%Y-%m-%d).log
```

### "The Python script has a bug"

The script is intentionally simple (~300 lines, stdlib only). Edit
`fetch-sources.py` directly. Each handler (`handle_rss_or_atom`,
`handle_github_releases`, etc.) returns `(items, error, state_update)` and is
easy to extend.

## What counts as "success"

A cron run is successful if it writes a draft file to
`../raw/shared/weekly-updates/<week>/<category>-draft.md`, even if individual
sources errored. The "Sources with errors" section of the draft tells you
what failed. You fix stale URLs during the Friday review or inline when you
notice them.

Total silence = cron didn't run at all. Check `crontab -l` and the system
cron log (`journalctl -u cron` on systemd systems).

## The Friday review

Scripts here don't do synthesis. The interactive Friday review does. Open
Claude in the wiki directory and paste `weekly-review-prompt.md`:

```bash
cd ~/Documents/magento-wiki
claude
```

Claude reads the week's drafts, produces a one-page brief (`review.md`),
and proposes which items to file into the real wiki as concepts/patterns/
decisions. You approve each filing. Total time: ~20 minutes/week.

## Related

- Workflow doc: `../raw/shared/weekly-updates/README.md`
- Wiki schema: `../CLAUDE.md`
- Friday review prompt: `./weekly-review-prompt.md`
