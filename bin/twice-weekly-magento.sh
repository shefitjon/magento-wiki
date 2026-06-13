#!/usr/bin/env bash
# twice-weekly-magento.sh — fetch Magento + security sources.
# Cron: Tuesday 07:00 and Friday 07:00.
# Security is bundled here because the user asked for Magento latest + security
# on the same 2x/week cadence. Runs two category fetches back-to-back.

cd "$(dirname "$0")/.." || exit 1
mkdir -p bin/logs
LOG="bin/logs/magento-$(date +%Y-%m-%d).log"
{
    echo "=== $(date --iso-8601=seconds) === twice-weekly-magento ==="
    python3 bin/fetch-sources.py --category magento
    rc1=$?
    echo "--- magento exit $rc1 ---"
    python3 bin/fetch-sources.py --category security
    rc2=$?
    echo "--- security exit $rc2 ---"
    echo "=== done (magento=$rc1, security=$rc2) ==="
} >> "$LOG" 2>&1
