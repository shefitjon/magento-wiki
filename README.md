# magento-wiki

A personal Magento 2 / Hyvä **second brain** and automation shell, maintained by
Claude Code and browsed in Obsidian, following Karpathy's LLM-wiki pattern with an
L1/L2 cache split.

> **This repository is intentionally minimal.** Project- and client-specific
> knowledge (the `raw/` area), shared rules/patterns/concepts, the schema, and all
> credentials are kept **local only** and are not published here. What lives in this
> repo is the non-confidential automation layer.

## What's here

- `bin/` — zero-cost source-fetching automation (Python standard library only, no
  API keys, no LLM calls). Cron scripts pull public RSS/Atom/GitHub-release/NVD-CVE
  feeds for the Hyvä / Magento / security / adjacent-stack ecosystem and stage
  markdown drafts for a later human review session.
  - `fetch-sources.py` + `sources.json` — the fetcher and its public source list.
  - `weekly-hyva.sh`, `twice-weekly-magento.sh`, `monthly-adjacent.sh`,
    `run-all.sh` — cron wrappers by cadence.
  - `wiki-dashboard.py` — a read-only health summary of the local vault.
  - `session-prompt.sh`, `wiki-reminder.sh` — local review-cadence helpers.
  - `README.md` — cron install instructions.

## Why a repo at all

The local vault doesn't need git to function. This repo exists so the
non-confidential automation can run from places that need an online source — e.g. a
scheduled cloud job that fetches the week's public Magento / Hyvä / security updates
and sends a digest.

## Layout of the full (local) vault

The complete second brain — kept on disk, not here — is organized as `CLAUDE.md`
(schema), `index.md` (catalog), `log.md` (audit trail), `raw/` (per-project state),
`rules/`, `concepts/`, and `patterns/`.
