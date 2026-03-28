#!/usr/bin/env python3
"""
Generate data/schedule/<month>_<year>_schedule.json for each month listed in MONTHS.
Edit the resulting JSON files to swap out any articles you don't like.
Run again after editing articles.json to regenerate, then re-apply manual edits.
"""

import json
import random
import calendar
import re
from pathlib import Path

MONTHS           = [(2026, 3), (2026, 4)]
ARTICLES_PER_DAY = 10

SKIP_PREFIXES = re.compile(
    r"^(lists? of|category:|wikipedia:|template:|portal:|file:|help:)",
    re.IGNORECASE,
)

# ── Load & clean article pool ─────────────────────────────────────────────────

raw = json.loads(Path("data/articles.json").read_text(encoding="utf-8"))

# Deduplicate by title, filter namespace/list pages
seen = set()
articles = []
for a in raw:
    t = a["title"]
    if t in seen:
        continue
    if SKIP_PREFIXES.match(t):
        continue
    seen.add(t)
    articles.append(a)

titles = [a["title"] for a in articles]
print(f"Article pool: {len(titles)} unique articles after filtering\n")

# ── Generate schedule per month ───────────────────────────────────────────────

schedule_dir = Path("data/schedule")
schedule_dir.mkdir(parents=True, exist_ok=True)

for year, month in MONTHS:
    month_name = calendar.month_name[month].lower()
    out_path   = schedule_dir / f"{month_name}_{year}_schedule.json"

    # Each month gets its own deterministic shuffle so months never overlap
    rng = random.Random(year * 10000 + month * 100)
    shuffled = titles[:]
    rng.shuffle(shuffled)

    days_in_month = calendar.monthrange(year, month)[1]
    schedule = {}
    for day in range(1, days_in_month + 1):
        start = (day - 1) * ARTICLES_PER_DAY
        schedule[str(day)] = shuffled[start : start + ARTICLES_PER_DAY]

    out_path.write_text(
        json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Written {out_path}  ({days_in_month} days × {ARTICLES_PER_DAY} articles)")
    for day in range(1, days_in_month + 1):
        arts = schedule[str(day)]
        print(f"  {year}-{month:02d}-{day:02d}: {', '.join(arts)}")
    print()
