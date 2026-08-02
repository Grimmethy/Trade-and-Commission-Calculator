#!/usr/bin/env python
"""Import WarhammerScraper xlsx catalogs into trade-calculator's SQLite DB.

Walks every IP (WH40k, Age of Sigmar, Horus Heresy) under WarhammerScraper's data/
directory. Faction titles and IP grouping come from WarhammerScraper's own
factions/*.py registry, not folder names — the disk layout doesn't reliably map to
either (an AoS "Chaos" folder holds several unrelated armies; a stray top-level
data/Destruction/ duplicates a file that actually lives under data/WH Sigmar/).

Usage:
    python scripts/import_catalog.py --scraper-root "F:\\GitHub\\WarhammerScraper"
    python scripts/import_catalog.py --scraper-root "..." --seed-out data/catalog_seed.json
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog_import import dump_seed_json, iter_catalog_rows, load_faction_lookup, upsert_rows
from app.db import SCHEMA


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scraper-root", required=True, help="Path to the WarhammerScraper repo (contains data/ and factions/)"
    )
    parser.add_argument("--db", default="trade.db", help="Path to the SQLite DB file")
    parser.add_argument("--seed-out", default=None, help="Also write a JSON seed snapshot to this path")
    args = parser.parse_args()

    scraper_root = Path(args.scraper_root)
    data_dir = scraper_root / "data"
    if not data_dir.is_dir():
        print(f"data/ directory not found under {scraper_root}", file=sys.stderr)
        sys.exit(1)

    faction_lookup = load_faction_lookup(scraper_root)
    if not faction_lookup:
        print("No factions found in WarhammerScraper's registry — check --scraper-root", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(args.db)
    conn.executescript(SCHEMA)

    rows = list(iter_catalog_rows(data_dir, faction_lookup))
    if not rows:
        print("No product rows found — check the source path and xlsx column layout.", file=sys.stderr)
        sys.exit(1)

    count = upsert_rows(conn, rows)
    by_ip = {}
    for row in rows:
        by_ip.setdefault(row["ip"], set()).add(row["faction"])
    for ip_name, factions in sorted(by_ip.items()):
        print(f"  {ip_name}: {len(factions)} factions")
    print(f"Imported/updated {count} catalog items from {data_dir}")

    if args.seed_out:
        seed_path = Path(args.seed_out)
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seeded = dump_seed_json(conn, seed_path)
        print(f"Wrote {seeded} catalog items to seed file: {seed_path}")

    conn.close()


if __name__ == "__main__":
    main()
