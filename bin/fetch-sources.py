#!/usr/bin/env python3
"""
fetch-sources.py — cron-friendly source fetcher for magento-wiki weekly updates.

Fetches RSS, Atom, GitHub release, NVD CVE, and HTML sources defined in
sources.json and writes drafts to raw/shared/weekly-updates/<week>/<cat>-draft.md.

No LLM calls. No API keys. Python standard library only.

Usage:
    python3 bin/fetch-sources.py --category hyva
    python3 bin/fetch-sources.py --category magento
    python3 bin/fetch-sources.py --category security
    python3 bin/fetch-sources.py --category adjacent
    python3 bin/fetch-sources.py --category all --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WIKI_ROOT = SCRIPT_DIR.parent
SOURCES_FILE = SCRIPT_DIR / "sources.json"
STATE_FILE = SCRIPT_DIR / ".fetch-state.json"
OUTPUT_BASE = WIKI_ROOT / "raw" / "shared" / "weekly-updates"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 60
MAX_ITEMS_PER_SOURCE = 20
MAX_SEEN_TRACKED = 200


def utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_week_folder() -> str:
    year, week, _ = datetime.date.today().isocalendar()
    return f"{year}-W{week:02d}"


def fetch_url(url: str) -> bytes:
    # curl-first: it's bounded by -m and reliable everywhere (some network stacks
    # hang Python's urllib past its own timeout). Fall back to stdlib urllib only
    # if curl isn't installed, so the script still works without it.
    try:
        out = subprocess.run(
            ["curl", "-fsSL", "-m", str(HTTP_TIMEOUT), "-A", USER_AGENT, url],
            capture_output=True, timeout=HTTP_TIMEOUT + 10,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout
        raise RuntimeError(
            f"curl exit {out.returncode}: {out.stderr.decode('utf-8', 'replace')[:200]}"
        )
    except FileNotFoundError:
        pass
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        raw = path.read_text()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"failed to parse {path}: {e}", file=sys.stderr)
        return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def strip_comment_keys(obj):
    if isinstance(obj, dict):
        return {
            k: strip_comment_keys(v)
            for k, v in obj.items()
            if not k.startswith("_")
        }
    if isinstance(obj, list):
        return [strip_comment_keys(i) for i in obj]
    return obj


def handle_rss_or_atom(source, state):
    try:
        body = fetch_url(source["url"]).decode("utf-8", errors="replace")
    except Exception as e:
        return [], f"fetch failed: {e}", {}
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return [], f"xml parse failed: {e}", {}

    items = []

    for item in root.iter("item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pub_date": (item.findtext("pubDate") or "").strip(),
                "summary": (item.findtext("description") or "").strip()[:300],
            }
        )

    if not items:
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(f"{ns}entry"):
            link_el = entry.find(f"{ns}link")
            link = link_el.get("href", "") if link_el is not None else ""
            items.append(
                {
                    "title": (entry.findtext(f"{ns}title") or "").strip(),
                    "link": link,
                    "pub_date": (entry.findtext(f"{ns}updated") or "").strip(),
                    "summary": (entry.findtext(f"{ns}summary") or "").strip()[:300],
                }
            )

    if not items:
        return [], "no <item> or <entry> found in feed", {}

    seen = set(state.get(source["name"], {}).get("seen_links", []))
    new_items = [i for i in items if i["link"] and i["link"] not in seen]
    updated_seen = sorted(
        seen | {i["link"] for i in items if i["link"]}
    )[-MAX_SEEN_TRACKED:]
    return new_items[:MAX_ITEMS_PER_SOURCE], None, {"seen_links": updated_seen}


def handle_github_releases(source, state):
    url = f"https://api.github.com/repos/{source['repo']}/releases"
    try:
        body = fetch_url(url).decode("utf-8", errors="replace")
        releases = json.loads(body)
    except urllib.error.HTTPError as e:
        return [], f"github api http {e.code}: {e.reason}", {}
    except Exception as e:
        return [], f"fetch failed: {e}", {}
    if not isinstance(releases, list):
        msg = releases.get("message", str(releases)[:100]) if isinstance(releases, dict) else str(releases)[:100]
        return [], f"unexpected response: {msg}", {}

    items = []
    for r in releases[:15]:
        body_text = (r.get("body") or "")[:400]
        body_text = body_text.replace("\r\n", " ").replace("\n", " ")
        items.append(
            {
                "title": r.get("name") or r.get("tag_name") or "(unnamed release)",
                "link": r.get("html_url", ""),
                "pub_date": r.get("published_at", ""),
                "summary": body_text,
            }
        )

    seen = set(state.get(source["name"], {}).get("seen_tags", []))
    new_items = [i for i in items if i["link"] and i["link"] not in seen]
    updated_seen = sorted(
        seen | {i["link"] for i in items if i["link"]}
    )[-MAX_SEEN_TRACKED:]
    return new_items[:MAX_ITEMS_PER_SOURCE], None, {"seen_tags": updated_seen}


def handle_nvd_cve(source, state):
    keywords = source.get("keywords", [])
    if not keywords:
        return [], "no keywords configured", {}

    items = []
    seen_in_run = set()
    since = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)
    ).strftime("%Y-%m-%dT00:00:00.000")
    until = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT00:00:00.000"
    )

    for kw in keywords:
        url = (
            "https://services.nvd.nist.gov/rest/json/cves/2.0"
            f"?keywordSearch={urllib.parse.quote(kw)}"
            f"&pubStartDate={since}&pubEndDate={until}"
        )
        try:
            data = json.loads(fetch_url(url).decode("utf-8", errors="replace"))
        except Exception as e:
            return items, f"NVD fetch failed for '{kw}': {e}", {}

        for v in data.get("vulnerabilities", []):
            cve = v.get("cve", {})
            cve_id = cve.get("id")
            if not cve_id or cve_id in seen_in_run:
                continue
            seen_in_run.add(cve_id)
            descs = cve.get("descriptions", [])
            desc = next((d["value"] for d in descs if d.get("lang") == "en"), "")
            cvss_metrics = cve.get("metrics", {}).get("cvssMetricV31") or []
            score = None
            if cvss_metrics:
                score = cvss_metrics[0].get("cvssData", {}).get("baseScore")
            summary = f"CVSS {score}: " if score else ""
            summary += desc[:280]
            items.append(
                {
                    "title": cve_id,
                    "link": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "pub_date": cve.get("published", ""),
                    "summary": summary,
                }
            )

    seen = set(state.get(source["name"], {}).get("seen_cves", []))
    new_items = [i for i in items if i["title"] not in seen]
    updated_seen = sorted(seen | {i["title"] for i in items})[-MAX_SEEN_TRACKED:]
    return new_items[:MAX_ITEMS_PER_SOURCE], None, {"seen_cves": updated_seen}


def handle_html(source, state):
    try:
        body = fetch_url(source["url"]).decode("utf-8", errors="replace")
    except Exception as e:
        return [], f"fetch failed: {e}", {}

    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    last_hash = state.get(source["name"], {}).get("last_hash")

    if last_hash == h:
        return [], None, {"last_hash": h}

    dump_dir = OUTPUT_BASE / iso_week_folder() / "raw-html"
    dump_dir.mkdir(parents=True, exist_ok=True)
    dump_path = dump_dir / f"{source['name']}.html"
    dump_path.write_text(body, encoding="utf-8")

    item = {
        "title": f"{source['name']} page changed",
        "link": source["url"],
        "pub_date": utcnow_iso(),
        "summary": (
            f"Raw HTML staged at {dump_path.relative_to(WIKI_ROOT)}. "
            f"Previous hash: {last_hash or 'none'}, new: {h}. "
            f"Review during Friday session."
        ),
    }
    return [item], None, {"last_hash": h}


HANDLERS = {
    "rss": handle_rss_or_atom,
    "atom": handle_rss_or_atom,
    "github-releases": handle_github_releases,
    "nvd-cve": handle_nvd_cve,
    "html": handle_html,
}


def write_draft(category, sources, results, errors):
    week = iso_week_folder()
    out_dir = OUTPUT_BASE / week
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{category}-draft.md"

    now = utcnow_iso()
    lines = [
        "---",
        "type: weekly-update-draft",
        "project: shared",
        f"category: {category}",
        "status: draft",
        f"generated: {now}",
        f"week: {week}",
        "---",
        "",
        f"# {category.capitalize()} weekly update draft — {week}",
        "",
        f"Generated `{now}` by `bin/fetch-sources.py --category {category}`.",
        "",
        "Raw fetches staged for triage during the Friday weekly review.",
        "This is **not** a wiki page — it will be summarized into `review.md`.",
        "",
        "## Sources checked",
        "",
    ]

    for s in sources:
        note = s.get("note", "")
        lines.append(f"- `{s['name']}` ({s['type']}) — {note}")
    lines.append("")

    lines.append("## What's new")
    lines.append("")

    any_new = False
    for s in sources:
        items = results.get(s["name"], [])
        if not items:
            continue
        any_new = True
        lines.append(f"### `{s['name']}`")
        lines.append("")
        for item in items:
            title = (item.get("title") or "(no title)").replace("\n", " ")
            link = item.get("link", "")
            pub = item.get("pub_date", "")
            summary = (item.get("summary") or "").strip().replace("\n", " ")
            head = f"- **{title}**"
            if pub:
                head += f" — _{pub}_"
            if link:
                head += f" — [link]({link})"
            lines.append(head)
            if summary:
                lines.append(f"  - {summary}")
        lines.append("")

    if not any_new:
        lines.append("_No new items from any source this run._")
        lines.append("")

    if errors:
        lines.append("## Sources with errors")
        lines.append("")
        for name, err in errors.items():
            lines.append(f"- `{name}` — {err}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def append_log(category, out_path, errors, new_count):
    log_file = WIKI_ROOT / "log.md"
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    err_note = f", {len(errors)} errors" if errors else ""
    rel = out_path.relative_to(WIKI_ROOT)
    entry = (
        f"\n## [{ts}] fetch | shared | cron: {category} ({new_count} new{err_note})\n"
        f"- Drafted to `{rel}`\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def run_category(cat: str, sources, state, dry_run: bool) -> tuple[int, int]:
    results = {}
    errors = {}

    for s in sources:
        handler = HANDLERS.get(s["type"])
        if handler is None:
            errors[s["name"]] = f"unknown source type '{s['type']}'"
            continue
        try:
            items, err, state_update = handler(s, state)
        except Exception as e:
            errors[s["name"]] = f"unexpected error: {type(e).__name__}: {e}"
            continue

        if err:
            errors[s["name"]] = err
            if not items:
                continue

        results[s["name"]] = items

        if not dry_run:
            entry = state.setdefault(s["name"], {})
            entry.update(state_update)
            entry["last_fetched"] = utcnow_iso()

    new_count = sum(len(v) for v in results.values())

    if dry_run:
        print(
            f"[{cat}] DRY RUN: {new_count} new items across "
            f"{len(sources)} sources, {len(errors)} errors"
        )
        for name, err in errors.items():
            print(f"  ERROR {name}: {err}")
    else:
        out_path = write_draft(cat, sources, results, errors)
        append_log(cat, out_path, errors, new_count)
        print(
            f"[{cat}] wrote {out_path.relative_to(WIKI_ROOT)} "
            f"({new_count} new items, {len(errors)} errors)"
        )

    return new_count, len(errors)


def main():
    available_cats = []
    if SOURCES_FILE.exists():
        available_cats = [
            c for c in strip_comment_keys(load_json(SOURCES_FILE, {})).keys()
            if not c.startswith("_")
        ]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category",
        required=True,
        choices=available_cats + ["all"],
        help="Source category to fetch (categories read from sources.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report, but do not write draft files or update state",
    )
    args = parser.parse_args()

    if not SOURCES_FILE.exists():
        print(f"sources.json not found at {SOURCES_FILE}", file=sys.stderr)
        return 1

    sources_by_cat = strip_comment_keys(load_json(SOURCES_FILE, {}))
    state = load_json(STATE_FILE, {})

    if args.category == "all":
        cats = [c for c in sources_by_cat.keys() if not c.startswith("_")]
    else:
        cats = [args.category]

    total_errors = 0
    total_new = 0
    for cat in cats:
        sources = sources_by_cat.get(cat, [])
        if not sources:
            print(f"no sources configured for category '{cat}'")
            continue
        new, errs = run_category(cat, sources, state, args.dry_run)
        total_new += new
        total_errors += errs

    if not args.dry_run:
        save_json(STATE_FILE, state)

    print(f"DONE. total new items: {total_new}, total errors: {total_errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
