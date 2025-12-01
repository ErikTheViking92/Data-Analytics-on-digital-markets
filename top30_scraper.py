"""Download data about the top N Steam games and their recent patches.

Workflow:
- Reads Steam API key from `APIkey.txt` (single line with the key). If missing, proceeds without key.
- Scrapes `https://steamcharts.com/top` to get the top games (by concurrent players).
- For each top appid, fetches:
  - Store metadata via `scraper.store_scraper.SteamStoreScraper`
  - Recent news via Steam Web API `ISteamNews/GetNewsForApp/v2` (uses API key if present)
  - Current players via `ISteamUserStats/GetNumberOfCurrentPlayers/v1`

Outputs `top30_results.json` and `top30_results.csv` by default.
"""
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import re
import json
import csv
import os
from datetime import datetime

from scraper.store_scraper import SteamStoreScraper
from scraper.steamdb_scraper import SteamDBScraper
from scraper.cache import SteamCache


STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
STEAM_PLAYERCOUNT_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"


def read_api_key(path: str = "APIkey.txt") -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        key = f.read().strip()
        return key or None


def fetch_top_from_steamcharts(n: int = 30) -> List[dict]:
    url = "https://steamcharts.com/top"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "steam-scraper/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    # rows are in table with class 'common-table' or simply 'main' — find the first table body
    table = soup.find("table")
    if not table:
        return results
    for tr in table.find_all("tr")[1: n + 1]:
        a = tr.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        # look for '/app/<appid>'
        m = re.search(r"/app/(\d+)", href)
        if not m:
            continue
        appid = int(m.group(1))
        name = a.get_text(strip=True)
        results.append({"appid": appid, "name": name})
        if len(results) >= n:
            break
    return results


def fetch_news_for_app(appid: int, api_key: Optional[str] = None, count: int = 20) -> List[dict]:
    params = {"appid": appid, "count": count, "maxlength": 1000}
    if api_key:
        params["key"] = api_key
    resp = requests.get(STEAM_NEWS_URL, params=params, timeout=10, headers={"User-Agent": "steam-scraper/1.0"})
    resp.raise_for_status()
    data = resp.json()
    return data.get("appnews", {}).get("newsitems", [])


def fetch_current_players(appid: int) -> Optional[int]:
    try:
        resp = requests.get(STEAM_PLAYERCOUNT_URL, params={"appid": appid}, timeout=8, headers={"User-Agent": "steam-scraper/1.0"})
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("player_count")
    except Exception:
        return None


def collect_top_n(n: int = 30, out_json: str = "top30_results.json", out_csv: str = "top30_results.csv", use_cache: bool = True):
    api_key = read_api_key()
    print(f"Using API key: {'present' if api_key else 'none'}")

    cache = SteamCache() if use_cache else None
    if cache:
        stats = cache.get_stats()
        print(f"Cache: {stats['total']} entries")

    tops = fetch_top_from_steamcharts(n)
    print(f"Found {len(tops)} top games from SteamCharts")

    store = SteamStoreScraper(cache=cache)
    steamdb = SteamDBScraper(cache=cache)

    rows = []
    for item in tops:
        aid = item["appid"]
        print(f"Processing {aid} - {item.get('name')}")
        entry = {"appid": aid, "name": item.get("name"), "collected_at": datetime.utcnow().isoformat()}

        # store metadata
        try:
            entry["store"] = store.fetch_app(aid)
        except Exception as e:
            entry["store"] = None
            entry["store_error"] = str(e)

        # steamdb best-effort
        try:
            sdb = steamdb.fetch_app(aid)
            entry["steamdb"] = sdb
        except Exception as e:
            entry["steamdb"] = None
            entry["steamdb_error"] = str(e)

        # news
        try:
            news = fetch_news_for_app(aid, api_key=api_key, count=10)
            entry["news"] = news
        except Exception as e:
            entry["news"] = None
            entry["news_error"] = str(e)

        # current players
        try:
            pc = fetch_current_players(aid)
            entry["current_players"] = pc
        except Exception:
            entry["current_players"] = None

        rows.append(entry)

    # write JSON
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # write CSV summary
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["appid", "name", "current_players", "store_name", "owners_estimate", "news_count"])
        for r in rows:
            store_name = None
            owners = None
            if r.get("store"):
                store_name = r["store"].get("name")
            if r.get("steamdb"):
                owners = r["steamdb"].get("owners")
            news_count = len(r.get("news") or [])
            writer.writerow([r.get("appid"), r.get("name"), r.get("current_players"), store_name, owners, news_count])

    print(f"Wrote {len(rows)} entries to {out_json} and {out_csv}")


if __name__ == "__main__":
    collect_top_n(30)
