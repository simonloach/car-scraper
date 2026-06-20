#!/usr/bin/env python3
"""Clean corrupted listing data.

The old scraper regex-scraped individual advert pages and occasionally produced
junk: prices with digits concatenated from unrelated page elements (e.g.
54 443 760 zł), and it never excluded the LC 500h V6 hybrid we don't care about.

This script, run once over a model file, does the obvious data engineering:
  1. drops listings whose title matches an excluded variant (e.g. "500h"),
  2. sanitizes each price_reading against sane per-model bounds, dropping
     out-of-range readings (the concatenation bugs) and recomputing
     current/initial price + price_change from what survives,
  3. drops a listing entirely if no valid price reading remains.

It prints a report and writes a .pre-clean backup. New data from the rewritten
scraper reads otomoto's structured price field and never has these bugs.

Usage:
    python scripts/clean_data.py data/lexus-lc/lexus-lc.json \
        --min 120000 --max 1500000 --exclude 500h
"""

import argparse
import json
import shutil
from pathlib import Path


def clean(data_file: Path, price_min: int, price_max: int, exclude: list[str]) -> dict:
    """Clean one model file; return {data, report, before, after} (no write)."""
    data = json.loads(data_file.read_text(encoding="utf-8"))
    if not (isinstance(data, dict) and "listings" in data):
        raise SystemExit(f"{data_file} is not in the expected {{listings: ...}} format")

    listings = data["listings"]
    report: dict = {"removed_variant": [], "removed_no_price": [], "fixed_readings": []}
    kept = {}

    for lid, l in listings.items():
        title = (l.get("title") or "").lower()
        if any(x.lower() in title for x in exclude):
            report["removed_variant"].append(
                (lid, l.get("title"), l.get("current_price"))
            )
            continue

        # Sanitize price history.
        readings = l.get("price_readings") or []
        good = [
            r
            for r in readings
            if isinstance(r, list)
            and len(r) == 2
            and isinstance(r[1], (int, float))
            and price_min <= r[1] <= price_max
        ]
        dropped = [r for r in readings if r not in good]

        if not good:
            # Fall back to current_price if it is itself sane (no readings case).
            cp = l.get("current_price")
            if isinstance(cp, (int, float)) and price_min <= cp <= price_max:
                ts = (
                    l.get("last_scrape_timestamp")
                    or l.get("first_scrape_timestamp")
                    or 0
                )
                good = [[ts, cp]]
            else:
                report["removed_no_price"].append((lid, l.get("title"), cp))
                continue

        if dropped:
            report["fixed_readings"].append(
                (lid, l.get("title"), [r[1] for r in dropped])
            )

        good.sort(key=lambda r: r[0])
        l["price_readings"] = good
        l["initial_price"] = good[0][1]
        l["current_price"] = good[-1][1]
        l["price_change"] = good[-1][1] - (good[-2][1] if len(good) > 1 else good[0][1])
        kept[lid] = l

    data["listings"] = kept
    data.setdefault("metadata", {})["total_listings"] = len(kept)
    return {"data": data, "report": report, "before": len(listings), "after": len(kept)}


def main() -> None:
    """CLI entry: clean a model file, print a report, write a backup."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_file", type=Path)
    ap.add_argument("--min", type=int, default=120_000, dest="price_min")
    ap.add_argument("--max", type=int, default=1_500_000, dest="price_max")
    ap.add_argument("--exclude", nargs="*", default=["500h"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = clean(args.data_file, args.price_min, args.price_max, args.exclude)
    r = out["report"]
    print(f"Listings: {out['before']} -> {out['after']}")
    print(f"Removed (excluded variant): {len(r['removed_variant'])}")
    for lid, title, price in r["removed_variant"]:
        print(f"  - {title}  ({price})")
    print(f"Removed (no valid price): {len(r['removed_no_price'])}")
    for lid, title, price in r["removed_no_price"]:
        print(f"  - {title}  (bad price: {price})")
    print(f"Fixed price readings (dropped junk): {len(r['fixed_readings'])}")
    for lid, title, bad in r["fixed_readings"]:
        print(f"  - {title}  dropped {bad}")

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return

    backup = args.data_file.with_suffix(args.data_file.suffix + ".pre-clean")
    shutil.copy2(args.data_file, backup)
    args.data_file.write_text(
        json.dumps(out["data"], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\nBackup: {backup}\nWrote:  {args.data_file}")


if __name__ == "__main__":
    main()
