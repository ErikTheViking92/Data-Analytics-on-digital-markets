"""Download data about the top 100 Steam games and their recent patches.

Workflow:
- Reads Steam API key from `APIkey.txt` (single line with the key). If missing, proceeds without key.
- Scrapes `https://store.steampowered.com/search/?sort_by=popular` to get the top games (by most played).
- For each top appid, fetches:
  - Store metadata via `scraper.store_scraper.SteamStoreScraper`
  - Recent news via Steam Web API `ISteamNews/GetNewsForApp/v2` (uses API key if present)
  - Current players via `ISteamUserStats/GetNumberOfCurrentPlayers/v1`

Outputs `top100_results.json` and `top100_results.csv` by default.
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


def fetch_top_most_played(n: int = 100) -> List[dict]:
    """Fetch top games from Steam Store search sorted by popular (most played)."""
    url = "https://store.steampowered.com/search/"
    params = {
        "os": "win",
        "sort_by": "popular",  # most played
        "count": n,  # try to get n results
    }
    resp = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    
    # Find all game rows in the search results
    for row in soup.find_all("a", class_="search_result_row"):
        if len(results) >= n:
            break
        
        # Extract appid from href like /app/570/
        href = row.get("href", "")
        m = re.search(r"/app/(\d+)/", href)
        if not m:
            continue
        appid = int(m.group(1))
        
        # Extract game name from title or text
        title_elem = row.find("span", class_="title")
        name = title_elem.get_text(strip=True) if title_elem else f"App {appid}"
        
        results.append({"appid": appid, "name": name})
    
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


def collect_top_n(n: int = 100, out_json: str = "top100_results.json", out_csv: str = "top100_results.csv", use_cache: bool = True):
    api_key = read_api_key()
    print(f"Using API key: {'present' if api_key else 'none'}")

    cache = SteamCache() if use_cache else None
    if cache:
        stats = cache.get_stats()
        print(f"Cache: {stats['total']} entries")

    tops = fetch_top_most_played(n)
    print(f"Found {len(tops)} top games from Steam Store Most Played")

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
    collect_top_n(100)
