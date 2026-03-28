#!/usr/bin/env python3
"""
Fetch the top 1000 most-read English Wikipedia articles by Belgian readers in 2025,
download their thumbnails, and write data/articles.json.
"""

import json
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path("data")
IMAGES_DIR = DATA_DIR / "images"
OUTPUT_FILE = DATA_DIR / "articles.json"

HEADERS = {"User-Agent": "WikipediaGame/1.0 (krijn@example.com)"}

# Pages that are not real articles
SKIP_PREFIXES = ("Special:", "Wikipedia:", "Help:", "Portal:", "File:", "Template:")
SKIP_TITLES = {"Main_Page", "-"}


def fetch_top_month(year: int, month: int) -> list[dict]:
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/"
        f"top/en.wikipedia/all-access/{year}/{month:02d}/all-days"
    )
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["items"][0]["articles"]


def collect_top_articles(year: int, top_n: int = 1000) -> list[dict]:
    """Aggregate en.wikipedia articles across all months, return top N by total views."""
    view_totals: dict[str, int] = {}

    for month in range(1, 13):
        print(f"  Fetching {year}-{month:02d} ...", end=" ", flush=True)
        try:
            articles = fetch_top_month(year, month)
        except requests.HTTPError as e:
            print(f"HTTP {e.response.status_code} — skipping")
            time.sleep(1)
            continue
        except Exception as e:
            print(f"Error: {e} — skipping")
            time.sleep(1)
            continue

        added = 0
        for art in articles:
            title = art["article"]
            if title in SKIP_TITLES:
                continue
            if any(title.startswith(p) for p in SKIP_PREFIXES):
                continue
            view_totals[title] = view_totals.get(title, 0) + art.get("views", 0)
            added += 1

        print(f"{added} articles")
        time.sleep(0.5)

    sorted_articles = sorted(view_totals.items(), key=lambda x: x[1], reverse=True)
    return [{"title": t, "total_views": v} for t, v in sorted_articles[:top_n]]


def fetch_wiki_summary(title: str) -> dict | None:
    encoded = requests.utils.quote(title, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def download_image(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"    Image download failed: {e}")
        return False


def main():
    DATA_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)

    print("=== Step 1: Collecting top articles (en.wikipedia, 2025) ===")
    top_articles = collect_top_articles(2025, top_n=1000)
    print(f"\nFound {len(top_articles)} unique articles\n")

    print("=== Step 2: Fetching summaries and downloading images ===")
    results = []

    for i, art in enumerate(top_articles, 1):
        title = art["title"]
        print(f"[{i:04d}/{len(top_articles)}] {title}", end=" ... ", flush=True)

        try:
            summary = fetch_wiki_summary(title)
        except Exception as e:
            print(f"summary error: {e} — skipping")
            time.sleep(0.5)
            continue

        if not summary:
            print("no summary — skipping")
            continue

        image_path = None
        thumbnail = summary.get("thumbnail")
        if thumbnail:
            safe_name = re.sub(r"[^\w\-.]", "_", title)[:100] + ".jpg"
            dest = IMAGES_DIR / safe_name
            if not dest.exists():  # skip re-download on re-runs
                download_image(thumbnail["source"], dest)
            if dest.exists():
                image_path = f"images/{safe_name}"

        results.append({
            "title": summary.get("title", title),
            "display_title": summary.get("displaytitle", title),
            "extract": summary.get("extract", ""),
            "image": image_path,
            "thumbnail_url": thumbnail["source"] if thumbnail else None,
            "wiki_url": summary.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "total_views_2025": art["total_views"],
        })

        print("ok" if image_path else "ok (no image)")
        time.sleep(0.2)

    print(f"\n=== Step 3: Writing {OUTPUT_FILE} ===")
    OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Saved {len(results)} articles.")

    total_bytes = sum(f.stat().st_size for f in IMAGES_DIR.iterdir() if f.is_file())
    print(f"Image storage: {total_bytes / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
