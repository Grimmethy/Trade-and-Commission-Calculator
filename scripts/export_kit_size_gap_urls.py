#!/usr/bin/env python
"""Prints the current kit-size gap queue as {slug: product_url}, ready to feed
into a browser-assisted scrape session (see WarhammerScraper's
scripts/scrape_kit_sizes.py). Ranked by how often people have actually tried
to trade the item, so the most-wanted units get scraped first.

Usage:
    python scripts/export_kit_size_gap_urls.py [--base-url http://127.0.0.1:8123]
"""
import argparse
import json
import sys
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8123")
    args = parser.parse_args()

    with urllib.request.urlopen(f"{args.base_url}/catalog/kit-size-gaps") as resp:
        data = json.load(resp)

    gaps = data["gaps"]
    urls = {g["item_name"]: g["website_link"] for g in gaps if g["website_link"]}

    print(json.dumps(urls, indent=2))
    print(f"\n{len(gaps)} items queued, ranked by demand:", file=sys.stderr)
    for g in gaps[:20]:
        print(f"  {g['times_selected']}x  {g['ip']} / {g['faction']} / {g['item_name']}", file=sys.stderr)


if __name__ == "__main__":
    main()
