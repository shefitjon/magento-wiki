#!/usr/bin/env bash
# weekly-hyva.sh — fetch Hyvä-related sources. Cron: Monday 07:00.
# Runs under cron: minimal environment, relative to script location.

cd "$(dirname "$0")/.." || exit 1
mkdir -p bin/logs
LOG="bin/logs/hyva-$(date +%Y-%m-%d).log"
{
    echo "=== $(date --iso-8601=seconds) === weekly-hyva ==="
    python3 bin/fetch-sources.py --category hyva
    rc=$?
    echo "=== exit $rc ==="
} >> "$LOG" 2>&1
