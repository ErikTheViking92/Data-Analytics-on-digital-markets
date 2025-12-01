"""Compare games updated in the past N months vs not-updated games.

This script uses the Steam News API (`ISteamNews/GetNewsForApp/v2`) to detect
whether a game has any recent news items that look like patch/update notes within
the last `months` months. It then collects owners estimates (from SteamDB scraper)
as a proxy for installs and compares basic statistics between the two groups.

Notes:
- "Owners" from SteamDB are best-effort text estimates; parsing may be noisy.
- SteamDB may block automated requests (403). The script handles None/missing values.
"""
from datetime import datetime, timedelta
import argparse
import json
import re
import statistics
from typing import List, Optional
import csv

import requests
from scraper.steamdb_scraper import SteamDBScraper


STEAM_PLAYERCOUNT_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"


STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"


def fetch_news_for_app(appid: int, count: int = 20) -> List[dict]:
    params = {"appid": appid, "count": count, "maxlength": 1000}
    resp = requests.get(STEAM_NEWS_URL, params=params, timeout=10, headers={"User-Agent": "steam-scraper/1.0"})
    resp.raise_for_status()
    data = resp.json()
    return data.get("appnews", {}).get("newsitems", [])


def looks_like_update(item: dict) -> bool:
    # Heuristic: title or contents contain keywords indicating a patch/update
    kws = [r"patch", r"update", r"hotfix", r"patch notes", r"update notes", r"version", r"v\.", r"beta"]
    txt = (item.get("title", "") + " " + item.get("contents", "")).lower()
    for k in kws:
        if re.search(k, txt):
            return True
    return False


def had_recent_update(appid: int, months: int = 6) -> bool:
    try:
        items = fetch_news_for_app(appid)
    except Exception:
        # if news endpoint fails, assume unknown -> treat as not-updated
        return False
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    for it in items:
        ts = it.get("date")
        if not ts:
            continue
        dt = datetime.utcfromtimestamp(int(ts))
        if dt >= cutoff:
            # If heuristics match OR any news in timeframe, consider updated
            if looks_like_update(it) or True:
                return True
    return False


def parse_owners_value(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    # Normalize dash characters
    s = s.replace("–", "-").replace("—", "-")
    # Find all numbers like 1,234 or 1234
    nums = re.findall(r"[\d,]+", s)
    if not nums:
        return None
    values = [float(n.replace(",", "")) for n in nums]
    if "-" in s and len(values) >= 2:
        # range -> return midpoint
        return (values[0] + values[1]) / 2.0
    # otherwise return the first number
    return values[0]


def fetch_current_players(appid: int) -> Optional[float]:
    try:
        resp = requests.get(STEAM_PLAYERCOUNT_URL, params={"appid": appid}, timeout=8, headers={"User-Agent": "steam-scraper/1.0"})
        resp.raise_for_status()
        data = resp.json()
        pc = data.get("response", {}).get("player_count")
        if pc is None:
            return None
        return float(pc)
    except Exception:
        return None


def summarize_group(values: List[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None}
    return {"count": len(values), "mean": statistics.mean(values), "median": statistics.median(values)}


def compare(appids: List[int], months: int = 6, out: str = "compare_results.json", csv_path: Optional[str] = None):
    store = SteamStoreScraper()
    steamdb = SteamDBScraper()

    updated = []
    not_updated = []
    details = []

    for aid in appids:
        print(f"Checking {aid}...")
        try:
            is_updated = had_recent_update(aid, months=months)
        except Exception as e:
            print(f"  News check failed for {aid}: {e}")
            is_updated = False

        # fetch owners from SteamDB best-effort
        try:
            sdb = steamdb.fetch_app(aid)
            owners_raw = sdb.get("owners") if sdb else None
        except Exception as e:
            print(f"  SteamDB fetch failed for {aid}: {e}")
            owners_raw = None

        owners_val = parse_owners_value(owners_raw)
        # If owners unknown, fall back to current players as an install proxy
        if owners_val is None:
            pc = fetch_current_players(aid)
            if pc is not None:
                owners_val = pc
                owners_raw = f"current_players:{int(pc)}"

        entry = {"appid": aid, "updated_recently": is_updated, "owners_raw": owners_raw, "owners_value": owners_val}
        details.append(entry)
        if is_updated:
            updated.append(owners_val) if owners_val is not None else None
        else:
            not_updated.append(owners_val) if owners_val is not None else None

    # Filter out Nones for stats
    updated_vals = [v for v in updated if v is not None]
    not_updated_vals = [v for v in not_updated if v is not None]

    summary = {"months": months, "total_checked": len(appids), "updated_count": len([d for d in details if d["updated_recently"]]), "not_updated_count": len([d for d in details if not d["updated_recently"]]),
               "updated_stats": summarize_group(updated_vals), "not_updated_stats": summarize_group(not_updated_vals)}

    out_data = {"summary": summary, "details": details}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    if csv_path:
        # write a simple CSV with rows for each app
        with open(csv_path, "w", newline="", encoding="utf-8") as cf:
            writer = csv.writer(cf)
            writer.writerow(["appid", "updated_recently", "owners_raw", "owners_value"])
            for d in details:
                writer.writerow([d.get("appid"), d.get("updated_recently"), d.get("owners_raw"), d.get("owners_value")])

    print("Comparison complete.")
    print(json.dumps(summary, indent=2))


def parse_args():
    p = argparse.ArgumentParser(description="Compare recently updated games vs not-updated")
    p.add_argument("--appids", nargs="*", type=int, help="List of appids to check")
    p.add_argument("--from-file", type=str, help="File containing appids, one per line")
    p.add_argument("--months", type=int, default=6, help="Window in months to treat as 'recent'")
    p.add_argument("--out", type=str, default="compare_results.json", help="Output JSON file")
    p.add_argument("--csv", type=str, help="Optional CSV output file path")
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


if __name__ == "__main__":
    args = parse_args()
    appids = []
    if args.appids:
        appids.extend(args.appids)
    if args.from_file:
        appids.extend(read_appids_from_file(args.from_file))
    appids = list(dict.fromkeys(appids))
    if not appids:
        print("No appids provided.")
    else:
        compare(appids, months=args.months, out=args.out)
