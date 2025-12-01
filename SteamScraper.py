"""CLI entrypoint for scraping Steam game metadata.

Usage examples:
    python SteamScraper.py --appids 570 730
    python SteamScraper.py --from-file ids.txt --out results.json

Outputs JSON by default.
"""
import argparse
import json
from typing import List

from scraper.store_scraper import SteamStoreScraper
from scraper.steamdb_scraper import SteamDBScraper


def parse_args():
    p = argparse.ArgumentParser(description="Scrape Steam Store and SteamDB metadata for appids")
    p.add_argument("--appids", nargs="*", type=int, help="List of numeric Steam appids to fetch")
    p.add_argument("--from-file", type=str, help="File with appids, one per line")
    p.add_argument("--out", type=str, default="results.json", help="Output JSON file path")
    p.add_argument("--no-steamdb", action="store_true", help="Skip SteamDB (best-effort) scraping")
    return p.parse_args()


def read_appids_from_file(path: str) -> List[int]:
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                ids.append(int(s))
            except ValueError:
                continue
    return ids


def main():
    args = parse_args()
    appids = []
    if args.appids:
        appids.extend(args.appids)
    if args.from_file:
        appids.extend(read_appids_from_file(args.from_file))
    appids = list(dict.fromkeys(appids))  # dedupe while preserving order

    if not appids:
        print("No appids provided. Use --appids or --from-file.")
        return

    store = SteamStoreScraper()
    steamdb = None if args.no_steamdb else SteamDBScraper()

    results = []
    for aid in appids:
        print(f"Fetching store data for {aid}...")
        store_data = store.fetch_app(aid)
        if not store_data:
            print(f"  Store data not found for {aid}")
            continue
        item = {"store": store_data}
        if steamdb:
            print(f"  Fetching SteamDB data for {aid}...")
            try:
                sdb = steamdb.fetch_app(aid)
                item["steamdb"] = sdb
            except Exception as e:
                print(f"  SteamDB fetch failed for {aid}: {e}")
                item["steamdb"] = None
        results.append(item)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Finished. Wrote {len(results)} entries to {args.out}")


if __name__ == "__main__":
    main()
