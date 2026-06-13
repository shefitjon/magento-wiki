#!/usr/bin/env bash
# monthly-adjacent.sh — fetch adjacent stack (Alpine, Tailwind, Magewire, web.dev).
# Cron: 1st of the month 07:00.
# Low priority, monthly cadence is plenty.

cd "$(dirname "$0")/.." || exit 1
mkdir -p bin/logs
LOG="bin/logs/adjacent-$(date +%Y-%m-%d).log"
{
    echo "=== $(date --iso-8601=seconds) === monthly-adjacent ==="
    python3 bin/fetch-sources.py --category adjacent
    rc=$?
    echo "=== exit $rc ==="
} >> "$LOG" 2>&1
