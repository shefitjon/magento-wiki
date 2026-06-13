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
echo "Run the Friday wiki review. Read this week's weekly-updates drafts and"
echo "log.md entries, then review the session summaries below for extractable"
echo "patterns. For each notable item propose a triage (concept / pattern /"
echo "decision / skill / skip) and wait for my approval before filing."
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
