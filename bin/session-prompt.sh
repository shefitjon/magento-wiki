#!/usr/bin/env bash
# session-prompt.sh — print a ready-to-paste Friday review starter prompt,
# seeded with this month's session-summaries entries. Read-only.
#   bash bin/session-prompt.sh
set -euo pipefail
WIKI="$(cd "$(dirname "$0")/.." && pwd)"
MONTH="$(date +%Y-%m)"
SUMMARY="$WIKI/raw/shared/session-summaries/$MONTH.md"

echo "===== Paste into a fresh Claude session inside the wiki ====="
echo
echo "Run the Friday wiki review. Read this week's weekly-updates drafts"
echo "(including creators-draft.md — Nate Herk's new videos) and log.md entries,"
echo "then review the session summaries below for extractable patterns. For each"
echo "notable item propose a triage (concept / pattern / decision / skill / skip)"
echo "and wait for my approval before filing."
echo
echo "ALSO include two sections (full spec in bin/weekly-review-prompt.md):"
echo "  - Creator watch — Nate Herk: list each new video (title + link + 1 clause)."
echo "  - What could make us better (level-up): from Nate's videos, cross-referenced"
echo "    against my ~/.claude/ skills + agents + hooks and the wiki, propose 1-3"
echo "    concrete adoptions (daily command / skill / subagent / wiki page). Be"
echo "    skeptical — skip generic AI-automation/n8n/lead-gen content that doesn't"
echo "    fit a solo Magento 2 / Hyvä / OpenMage frontend dev. Propose, don't build."
echo
echo "Rule of thumb from the skills plan: a class of problem seen twice becomes"
echo "a wiki pattern; seen three times becomes a skill."
echo
if [ -f "$SUMMARY" ]; then
  echo "--- This month's session summaries ($MONTH) ---"
  cat "$SUMMARY"
else
  echo "(No session-summaries file for $MONTH yet — nothing logged this month.)"
fi
echo
echo "============================================================"
