#!/usr/bin/env python3
"""
Fetch Wikipedia Vital Articles Level 5 (~50 000 articles) and save to:
  data/vital_l5.json  (L5-only — excludes titles already in L3 and L4)

This will take a long time to run (potentially several hours).
Used for Ultra Mode: 10 random L5 articles, not tied to a day.

Usage:
  python fetch_l5_articles.py
"""

import json
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path("data")
L3_FILE  = DATA_DIR / "vital_l3.json"
L4_FILE  = DATA_DIR / "vital_l4.json"
L5_FILE  = DATA_DIR / "vital_l5.json"

HEADERS = {"User-Agent": "WikipediaGame/1.0 (krijn@example.com)"}
API     = "https://en.wikipedia.org/w/api.php"

SKIP_PREFIXES = re.compile(
    r"^(lists? of|category:|wikipedia:|template:|portal:|file:|help:)",
    re.IGNORECASE,
)
SKIP_EXACT = {"Main Page", "-"}


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(params: dict) -> dict:
    resp = requests.get(API, params={**params, "format": "json"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_subpages(ns_prefix: str) -> list[str]:
    pages = []
    params = {
        "action": "query",
        "list": "allpages",
        "apnamespace": "4",
        "apprefix": ns_prefix,
        "aplimit": "max",
    }
    while True:
        data = api_get(params)
        for p in data["query"]["allpages"]:
            pages.append(p["title"])
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(0.1)
    return pages


def get_linked_articles(page_title: str) -> set[str]:
    data = api_get({
        "action": "parse",
        "page": page_title,
        "prop": "links",
        "redirects": "1",
    })
    return {
        link["*"]
        for link in data.get("parse", {}).get("links", [])
        if link.get("ns") == 0
    }


def collect_titles_from_prefix(ns_prefix: str) -> set[str]:
    source_pages = get_subpages(ns_prefix)
    source_pages = list(dict.fromkeys(source_pages))

    print(f"  Found {len(source_pages)} source pages for prefix '{ns_prefix}'")

    all_titles: set[str] = set()
    for i, page in enumerate(source_pages, 1):
        print(f"  [{i:03d}/{len(source_pages)}] {page}", end=" ... ", flush=True)
        try:
            found = get_linked_articles(page)
        except Exception as e:
            print(f"error: {e}")
            time.sleep(1)
            continue
        print(f"{len(found)} links")
        all_titles |= found
        time.sleep(0.2)

    return all_titles


def clean(titles: set[str]) -> list[str]:
    return sorted(
        t for t in titles
        if t not in SKIP_EXACT and not SKIP_PREFIXES.match(t)
    )


# ── Wikipedia summary ─────────────────────────────────────────────────────────

def fetch_wiki_summary(title: str) -> dict | None:
    encoded = requests.utils.quote(title, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def enrich(titles: list[str]) -> list[dict]:
    results = []
    for i, title in enumerate(titles, 1):
        print(f"[{i:05d}/{len(titles)}] {title}", end=" ... ", flush=True)
        try:
            summary = fetch_wiki_summary(title)
        except Exception as e:
            print(f"summary error: {e} — skipping")
            time.sleep(0.5)
            continue
        if not summary:
            print("no summary — skipping")
            continue

        results.append({
            "title":         summary.get("title", title),
            "display_title": summary.get("displaytitle", title),
            "extract":       summary.get("extract", ""),
            "wiki_url":      summary.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "vital_level":   "5",
        })
        print("ok")
        time.sleep(0.2)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(exist_ok=True)

    # Load existing L3 + L4 titles to exclude them
    existing: set[str] = set()
    for f in [L3_FILE, L4_FILE]:
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            existing |= {a["title"] for a in data}
    print(f"Loaded {len(existing)} existing L3+L4 titles to exclude\n")

    # ── Collect L5 titles ─────────────────────────────────────────────────────
    print("=== Step 1: Collecting Vital Articles Level 5 ===")
    l5_raw = collect_titles_from_prefix("Vital_articles/Level/5")
    l5_titles = clean(l5_raw - existing)
    print(f"\n→ {len(l5_titles)} unique L5-only titles after filtering\n")

    # ── Enrich & save ─────────────────────────────────────────────────────────
    print("=== Step 2: Enriching L5 articles ===")
    l5_data = enrich(l5_titles)
    L5_FILE.write_text(json.dumps(l5_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(l5_data)} L5 articles → {L5_FILE}")


if __name__ == "__main__":
    main()
