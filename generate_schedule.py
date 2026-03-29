#!/usr/bin/env python3
"""
Generate data/schedule/<month>_<year>_schedule.json for each month in MONTHS.

Each day gets 10 articles: 5 from Vital Level 3 (accessible), 5 from Level 4 (harder).
The split enables a future Hard Mode that draws only from Level 4.

Sources:
  data/vital_l3.json   (~1000 articles)
  data/vital_l4.json   (~10 000 articles, L4-only)
"""

import json
import random
import calendar
import re
from pathlib import Path

MONTHS = [
    (2026, 3), 
    (2026, 4), 
    (2026, 5),
    (2026, 6),
    (2026, 7),
    (2026, 8),
    (2026, 9),
    (2026, 10),
    (2026, 11),
    (2026, 12),
]

L3_PER_DAY = 3
L4_PER_DAY = 7
ARTICLES_PER_DAY = L3_PER_DAY + L4_PER_DAY

SKIP_PREFIXES = re.compile(
    r"^(lists? of|category:|wikipedia:|template:|portal:|file:|help:)",
    re.IGNORECASE,
)

# ── Load & clean article pools ────────────────────────────────────────────────

def load_pool(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    titles: list[str] = []
    for a in raw:
        t = a["title"]
        if t in seen or SKIP_PREFIXES.match(t):
            continue
        seen.add(t)
        titles.append(t)
    return titles

l3_titles = load_pool(Path("data/vital_l3.json"))
l4_titles = load_pool(Path("data/vital_l4.json"))

print(f"L3 pool: {len(l3_titles)} articles")
print(f"L4 pool: {len(l4_titles)} articles")

if len(l3_titles) < L3_PER_DAY * 31:
    print(f"WARNING: L3 pool has only {len(l3_titles)} articles — may repeat within a year")
if len(l4_titles) < L4_PER_DAY * 31:
    print(f"WARNING: L4 pool has only {len(l4_titles)} articles — may repeat within a year")

# ── Generate schedule per month ───────────────────────────────────────────────

schedule_dir = Path("data/schedule")
schedule_dir.mkdir(parents=True, exist_ok=True)

for year, month in MONTHS:
    month_name = calendar.month_name[month].lower()
    out_path   = schedule_dir / f"{month_name}_{year}_schedule.json"

    # Deterministic per month — changing the seed changes all schedules for that month
    rng = random.Random(year * 10000 + month * 100)

    l3_shuffled = l3_titles[:]
    l4_shuffled = l4_titles[:]
    rng.shuffle(l3_shuffled)
    rng.shuffle(l4_shuffled)

    days_in_month = calendar.monthrange(year, month)[1]
    schedule: dict[str, list[str]] = {}

    for day in range(1, days_in_month + 1):
        l3_start = (day - 1) * L3_PER_DAY
        l4_start = (day - 1) * L4_PER_DAY
        day_articles = (
            l3_shuffled[l3_start : l3_start + L3_PER_DAY]
            + l4_shuffled[l4_start : l4_start + L4_PER_DAY]
        )
        # Shuffle the combined list so L3/L4 aren't obviously grouped
        rng.shuffle(day_articles)
        schedule[str(day)] = day_articles

    out_path.write_text(
        json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nWritten {out_path}  ({days_in_month} days × {ARTICLES_PER_DAY} articles)")
    for day in range(1, days_in_month + 1):
        arts = schedule[str(day)]
        print(f"  {year}-{month:02d}-{day:02d}: {', '.join(arts)}")
