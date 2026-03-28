#!/usr/bin/env python3
"""
Fetch Wikipedia Vital Articles (Level 3 and Level 4) and save to:
  data/vital_l3.json  (~1000 articles)
  data/vital_l4.json  (~10 000 articles, L4-only — excludes L3 titles)

Also downloads thumbnails to data/images/.

Usage:
  python fetch_articles.py
"""

import json
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path("data")
L3_FILE  = DATA_DIR / "vital_l3.json"
L4_FILE  = DATA_DIR / "vital_l4.json"

HEADERS = {"User-Agent": "WikipediaGame/1.0 (krijn@example.com)"}
API     = "https://en.wikipedia.org/w/api.php"

# Titles that are navigation/disambiguation noise
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
    """
    Return all page titles in Wikipedia namespace (ns=4) whose name starts
    with `ns_prefix` (without the 'Wikipedia:' part).
    e.g. ns_prefix='Vital_articles/Level/3'
    """
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
    """Return all mainspace (ns=0) article titles linked from a project page.

    Uses action=parse so template-generated links (e.g. {{va|...}}) are included.
    action=parse returns the fully rendered link list in one shot — no pagination needed.
    """
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


def collect_titles_from_prefix(ns_prefix: str, extra_pages: list[str] | None = None) -> set[str]:
    """
    Discover all subpages under `ns_prefix`, plus any `extra_pages`,
    then collect every mainspace article linked from them.
    """
    source_pages = get_subpages(ns_prefix)
    if extra_pages:
        source_pages += extra_pages
    source_pages = list(dict.fromkeys(source_pages))  # deduplicate, preserve order

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


# ── Wikipedia summary + image ─────────────────────────────────────────────────

def fetch_wiki_summary(title: str) -> dict | None:
    encoded = requests.utils.quote(title, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()



def enrich(titles: list[str], label: str) -> list[dict]:
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
            "vital_level":   label,
        })
        print("ok")
        time.sleep(0.2)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(exist_ok=True)

    # ── Level 3 (~1000 articles) ──────────────────────────────────────────────
    print("=== Step 1: Collecting Vital Articles Level 3 ===")
    l3_raw = collect_titles_from_prefix(
        "Vital_articles/Level/3",
        extra_pages=["Wikipedia:Vital_articles"],   # the main L3 hub page
    )
    l3_titles = clean(l3_raw)
    print(f"\n→ {len(l3_titles)} unique L3 titles after filtering\n")

    # ── Level 4 (~10 000 articles, L4-only) ───────────────────────────────────
    print("=== Step 2: Collecting Vital Articles Level 4 ===")
    l4_raw = collect_titles_from_prefix("Vital_articles/Level/4")
    l4_titles = clean(l4_raw - l3_raw)   # exclude articles already in L3
    print(f"\n→ {len(l4_titles)} unique L4-only titles after filtering\n")

    # ── Enrich & save L3 ─────────────────────────────────────────────────────
    print("=== Step 3: Enriching L3 articles ===")
    l3_data = enrich(l3_titles, "3")
    L3_FILE.write_text(json.dumps(l3_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(l3_data)} L3 articles → {L3_FILE}\n")

    # ── Enrich & save L4 ─────────────────────────────────────────────────────
    print("=== Step 4: Enriching L4 articles ===")
    l4_data = enrich(l4_titles, "4")
    L4_FILE.write_text(json.dumps(l4_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(l4_data)} L4 articles → {L4_FILE}\n")



if __name__ == "__main__":
    main()
