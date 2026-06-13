#!/usr/bin/env bash
# run-all.sh — manually run every category. For testing, ad-hoc refreshes,
# or the very first fetch before cron is installed.
# NOT a cron entry — just a human convenience.

cd "$(dirname "$0")/.." || exit 1
mkdir -p bin/logs
LOG="bin/logs/run-all-$(date +%Y-%m-%d_%H-%M).log"
{
    echo "=== $(date --iso-8601=seconds) === run-all (manual) ==="
    python3 bin/fetch-sources.py --category all
    rc=$?
    echo "=== exit $rc ==="
} 2>&1 | tee "$LOG"
