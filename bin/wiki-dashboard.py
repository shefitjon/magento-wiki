#!/usr/bin/env python3
"""wiki-dashboard.py — one-screen health summary of the Magento wiki.

Read-only. Python stdlib only. NOT a cron script — run it interactively
(e.g. before the Friday review) to spot drift:
  python3 bin/wiki-dashboard.py

Reports: page counts by type, stale active pages (updated > 90 days),
pages missing required frontmatter, and unresolved session-summary entries.
"""
import os
import re
import sys
from datetime import date, datetime

WIKI = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STALE_DAYS = 90
SKIP_DIRS = {".git", ".obsidian", "node_modules", "raw/shared/weekly-updates"}

FM_RE = re.compile(r"^---\s*$")


def parse_frontmatter(path):
    fm = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return fm
    if not lines or not FM_RE.match(lines[0]):
        return fm
    for line in lines[1:]:
        if FM_RE.match(line):
            break
        m = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def iter_md():
    for root, dirs, files in os.walk(WIKI):
        rel = os.path.relpath(root, WIKI)
        dirs[:] = [d for d in dirs if os.path.join(rel, d).lstrip("./") not in SKIP_DIRS and d not in SKIP_DIRS]
        if any(skip in rel for skip in ("weekly-updates",)):
            continue
        for f in files:
            if f.endswith(".md"):
                yield os.path.join(root, f)


def main():
    today = date.today()
    by_type = {}
    stale = []
    missing_fm = []
    for path in iter_md():
        rel = os.path.relpath(path, WIKI)
        if os.path.basename(path) in ("README.md", "index.md", "log.md", "CLAUDE.md", "MEMORY.md"):
            continue
        # Intentionally frontmatter-free working files
        if rel.startswith("raw/shared/session-summaries/") or rel.startswith("bin/") or rel.startswith("raw/shared/plans/"):
            continue
        fm = parse_frontmatter(path)
        if not fm:
            missing_fm.append(rel)
            continue
        ptype = fm.get("type", "untyped")
        by_type[ptype] = by_type.get(ptype, 0) + 1
        upd = fm.get("updated", "")
        status = fm.get("status", "")
        if status == "active" and re.match(r"\d{4}-\d{2}-\d{2}", upd):
            try:
                age = (today - datetime.strptime(upd[:10], "%Y-%m-%d").date()).days
                if age > STALE_DAYS:
                    stale.append((age, rel))
            except ValueError:
                pass

    print(f"\n=== Magento wiki dashboard — {today} ===\n")
    print("Pages by type:")
    for t in sorted(by_type):
        print(f"  {t:16} {by_type[t]}")

    print(f"\nStale (status: active, updated > {STALE_DAYS}d ago): {len(stale)}")
    for age, rel in sorted(stale, reverse=True):
        print(f"  {age:4}d  {rel}")

    if missing_fm:
        print(f"\nMissing frontmatter: {len(missing_fm)}")
        for rel in missing_fm:
            print(f"  {rel}")

    sess = os.path.join(WIKI, "raw/shared/session-summaries")
    if os.path.isdir(sess):
        open_items = 0
        for f in sorted(os.listdir(sess)):
            if f.endswith(".md"):
                with open(os.path.join(sess, f), encoding="utf-8") as fh:
                    txt = fh.read()
                open_items += len(re.findall(r"Pattern gap\W*?:\s*yes(?!/)", txt, re.I))
        print(f"\nSession-summary entries flagged 'pattern gap: yes': {open_items}")

    print()


if __name__ == "__main__":
    sys.exit(main())
