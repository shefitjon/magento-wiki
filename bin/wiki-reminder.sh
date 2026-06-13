#!/usr/bin/env bash
# Local cron reminder for the Magento wiki cadence. NOT a cloud agent — it runs on
# THIS machine, so it can read the wiki, run the prep scripts, and fire a desktop
# notification. Zero LLM cost (stdlib + notify-send only), matching the bin/ cron ethos.
#   bin/wiki-reminder.sh friday    # Friday review starter
#   bin/wiki-reminder.sh monthly   # monthly session-summaries extract
set -uo pipefail
WIKI="$(cd "$(dirname "$0")/.." && pwd)"
KIND="${1:-}"
OUT="$WIKI/bin/reminders"
mkdir -p "$OUT"
STAMP="$(date +%F)"

notify() {
  local title="$1" body="$2"
  # cron has no desktop session; best-effort wire-up so notify-send reaches the GUI
  export DISPLAY="${DISPLAY:-:0}"
  export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
  command -v notify-send >/dev/null 2>&1 && notify-send -u normal "$title" "$body" 2>/dev/null
  echo "[$(date '+%F %H:%M')] $title — $body" >> "$OUT/reminders.log"
}

case "$KIND" in
  friday)
    f="$OUT/friday-$STAMP.txt"
    bash "$WIKI/bin/session-prompt.sh" > "$f" 2>&1
    notify "Magento wiki — Friday review" "Starter saved to $f. Open the wiki in Claude and paste it."
    ;;
  monthly)
    f="$OUT/monthly-$STAMP.txt"
    python3 "$WIKI/bin/wiki-dashboard.py" > "$f" 2>&1
    notify "Magento wiki — monthly extract" "Dashboard saved to $f. Skim session-summaries; promote repeats (2x -> pattern, 3x -> skill)."
    ;;
  *)
    echo "usage: $(basename "$0") friday|monthly" >&2
    exit 2
    ;;
esac
