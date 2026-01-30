"""Scrape top Steam games for staggered DiD analysis across Jan-Apr 2025.

Collects:
- Games with major patches in January 2025 (treatment group 1)
- Games with major patches in February 2025 (treatment group 2)
- Games with major patches in March 2025 (treatment group 3)
- Games with major patches in April 2025 (treatment group 4)
- Games without major patches in Jan-Apr 2025 (control group)

Target: Equal sample sizes per group (50 games each = 250 total)
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

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


def fetch_top_most_played(n: int = 100, start: int = 0) -> List[dict]:
    """Fetch top games from Steam Store search sorted by popular."""
    url = "https://store.steampowered.com/search/"
    params = {
        "os": "win",
        "sort_by": "popular",
        "count": min(n, 100),
        "start": start,
    }
    resp = requests.get(
        url,
        params=params,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    
    for row in soup.find_all("a", class_="search_result_row"):
        href = row.get("href", "")
        m = re.search(r"/app/(\d+)/", href)
        if not m:
            continue
        appid = int(m.group(1))
        
        title_elem = row.find("span", class_="title")
        name = title_elem.get_text(strip=True) if title_elem else f"App {appid}"
        
        results.append({"appid": appid, "name": name})
    
    return results


def fetch_news_for_app(appid: int, api_key: Optional[str] = None, count: int = 100) -> List[dict]:
    """Fetch news items for an app."""
    params = {"appid": appid, "count": count, "maxlength": 2000}
    if api_key:
        params["key"] = api_key
    
    try:
        resp = requests.get(
            STEAM_NEWS_URL,
            params=params,
            timeout=10,
            headers={"User-Agent": "steam-scraper/1.0"}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("appnews", {}).get("newsitems", [])
    except Exception as e:
        print(f"  Error fetching news for {appid}: {e}")
        return []


def fetch_current_players(appid: int) -> Optional[int]:
    """Fetch current player count."""
    try:
        resp = requests.get(
            STEAM_PLAYERCOUNT_URL,
            params={"appid": appid},
            timeout=8,
            headers={"User-Agent": "steam-scraper/1.0"}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("player_count")
    except Exception:
        return None


def classify_major_patch(title: str, contents: str) -> tuple[bool, Optional[str]]:
    """Classify if a news item is a major patch."""
    combined = (title + " " + contents).lower()
    
    patch_keywords = [
        "patch", "update", "hotfix", "fix", "bug", "balance", 
        "expansion", "dlc", "content update",
        "maintenance", "adjustment", "tweak", "improvement"
    ]
    is_patch = any(kw in combined for kw in patch_keywords)
    
    if not is_patch:
        return (False, None)
    
    # UPDATED KEYWORDS: More specific major patch indicators
    major_indicators = [
        "major update", "major patch", "big update", "massive update",
        "expansion", "new expansion", "dlc", "new dlc",
        "new game mode","new characters", "new weapons", "substantial", "significant", "massive",
        "season", "new season", "complete rework", "major rework", "major overhaul",
        "major release", "major content"
    ]
    
    minor_indicators = [
        "hotfix", "bug fix", "bugfix", "small fix", "minor fix",
        "minor", "small update", "small patch",
        "performance", "optimization", "performance fix",
        "cosmetic", "visual fix", "visual update",
        "balance adjustment", "balance tweak", "balance patch",
        "tweak", "adjustment", "stability", "crash fix"
    ]
    
    is_major_candidate = any(ind in combined for ind in major_indicators)
    is_minor_candidate = any(ind in combined for ind in minor_indicators)
    
    if is_minor_candidate and not is_major_candidate:
        return (False, "minor_keywords")
    elif is_major_candidate:
        return (True, "major_keywords")
    else:
        if "bug fix" in combined or "hotfix" in combined or "balance" in combined:
            return (False, "default_minor")
        elif "update" in combined and "content" not in combined:
            return (False, "generic_update")
        else:
            return (False, "unclear_patch")


def get_major_patches_by_month(appid: int, year: int, month: int, api_key: Optional[str] = None) -> List[dict]:
    """Get major patches for a specific month."""
    news = fetch_news_for_app(appid, api_key=api_key, count=100)
    
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(seconds=1)
    
    major_patches = []
    
    for item in news:
        unix_ts = item.get("date", 0)
        try:
            item_date = datetime.utcfromtimestamp(unix_ts)
        except Exception:
            continue
        
        if not (month_start <= item_date <= month_end):
            continue
        
        title = item.get("title", "")
        contents = item.get("contents", "")
        
        is_major, reason = classify_major_patch(title, contents)
        
        if is_major:
            major_patches.append({
                "title": title,
                "contents": contents[:500],
                "date": item_date.strftime("%Y-%m-%d %H:%M:%S"),
                "unix_timestamp": unix_ts,
                "classification_reason": reason
            })
    
    return major_patches


def collect_staggered_groups(
    games_per_group: int = 50,
    max_games_to_check: int = 2000,
    use_cache: bool = True
):
    """
    Collect treatment groups for Jan, Feb, Mar, Apr 2025 and control group.
    """
    api_key = read_api_key()
    print(f"Using API key: {'present' if api_key else 'none'}")
    print(f"Target: {games_per_group} games per group (5 groups = {games_per_group * 5} total)")
    print(f"Months: January, February, March, April 2025\n")

    cache = SteamCache() if use_cache else None
    if cache:
        stats = cache.get_stats()
        print(f"Cache: {stats['total']} entries\n")

    store = SteamStoreScraper(cache=cache)
    steamdb = SteamDBScraper(cache=cache)

    # Groups
    jan_group = []  # Treatment month = January 2025
    feb_group = []  # Treatment month = February 2025
    mar_group = []  # Treatment month = March 2025
    apr_group = []  # Treatment month = April 2025
    control_group = []  # No major patches in Jan-Apr 2025
    
    all_results = []
    games_checked = 0
    start_position = 0
    
    while (len(jan_group) < games_per_group or 
           len(feb_group) < games_per_group or 
           len(mar_group) < games_per_group or 
           len(apr_group) < games_per_group or 
           len(control_group) < games_per_group) and games_checked < max_games_to_check:
        
        batch = fetch_top_most_played(n=100, start=start_position)
        if not batch:
            print(f"\nNo more games at position {start_position}")
            break
        
        print(f"\nFetched {len(batch)} games (position {start_position})")
        start_position += len(batch)
        
        for item in batch:
            if all(len(g) >= games_per_group for g in [jan_group, feb_group, mar_group, apr_group, control_group]):
                break
            
            aid = item["appid"]
            name = item["name"]
            games_checked += 1
            
            print(f"[{games_checked}] {aid} - {name}")
            
            # Check each month (including December 2024)
            dec_patches = get_major_patches_by_month(aid, 2024, 12, api_key)
            jan_patches = get_major_patches_by_month(aid, 2025, 1, api_key)
            feb_patches = get_major_patches_by_month(aid, 2025, 2, api_key)
            mar_patches = get_major_patches_by_month(aid, 2025, 3, api_key)
            apr_patches = get_major_patches_by_month(aid, 2025, 4, api_key)
            
            has_dec = len(dec_patches) > 0
            has_jan = len(jan_patches) > 0
            has_feb = len(feb_patches) > 0
            has_mar = len(mar_patches) > 0
            has_apr = len(apr_patches) > 0
            has_any = has_jan or has_feb or has_mar or has_apr
            
            # Create entry
            entry = {
                "appid": aid,
                "name": name,
                "collected_at": datetime.utcnow().isoformat(),
                "dec_major_patches": dec_patches,
                "jan_major_patches": jan_patches,
                "feb_major_patches": feb_patches,
                "mar_major_patches": mar_patches,
                "apr_major_patches": apr_patches,
                "dec_count": len(dec_patches),
                "jan_count": len(jan_patches),
                "feb_count": len(feb_patches),
                "mar_count": len(mar_patches),
                "apr_count": len(apr_patches)
            }
            
            # Fetch store and steamdb
            try:
                entry["store"] = store.fetch_app(aid)
            except Exception as e:
                entry["store"] = None
                entry["store_error"] = str(e)
            
            try:
                entry["steamdb"] = steamdb.fetch_app(aid)
            except Exception as e:
                entry["steamdb"] = None
                entry["steamdb_error"] = str(e)
            
            try:
                entry["current_players"] = fetch_current_players(aid)
            except Exception:
                entry["current_players"] = None
            
            all_results.append(entry)
            
            # Assign to groups (priority: earliest month with patches, control if none)
            assigned = False
            
            if has_jan and len(jan_group) < games_per_group:
                jan_group.append(entry)
                print(f"  → JAN group (#{len(jan_group)}): {len(jan_patches)} patches")
                assigned = True
            elif has_feb and len(feb_group) < games_per_group:
                feb_group.append(entry)
                print(f"  → FEB group (#{len(feb_group)}): {len(feb_patches)} patches")
                assigned = True
            elif has_mar and len(mar_group) < games_per_group:
                mar_group.append(entry)
                print(f"  → MAR group (#{len(mar_group)}): {len(mar_patches)} patches")
                assigned = True
            elif has_apr and len(apr_group) < games_per_group:
                apr_group.append(entry)
                print(f"  → APR group (#{len(apr_group)}): {len(apr_patches)} patches")
                assigned = True
            elif not has_any and not has_dec and len(control_group) < games_per_group:
                # Control group: No patches in Dec 2024 - Apr 2025
                control_group.append(entry)
                print(f"  → CONTROL group (#{len(control_group)})")
                assigned = True
            else:
                if has_dec and not has_any:
                    print(f"  → Skipped (patches only in Dec 2024)")
                else:
                    print(f"  → Skipped")
            
            if assigned:
                print(f"  Progress: Jan={len(jan_group)}, Feb={len(feb_group)}, Mar={len(mar_group)}, Apr={len(apr_group)}, Control={len(control_group)}")
            
            time.sleep(0.1)  # Rate limiting
    
    # Save results
    print(f"\n{'='*80}")
    print("Collection complete!")
    print(f"January group: {len(jan_group)} games")
    print(f"February group: {len(feb_group)} games")
    print(f"March group: {len(mar_group)} games")
    print(f"April group: {len(apr_group)} games")
    print(f"Control group: {len(control_group)} games")
    print(f"Total games checked: {games_checked}")
    
    with open("staggered_jan_group.json", "w", encoding="utf-8") as f:
        json.dump(jan_group, f, ensure_ascii=False, indent=2)
    
    with open("staggered_feb_group.json", "w", encoding="utf-8") as f:
        json.dump(feb_group, f, ensure_ascii=False, indent=2)
    
    with open("staggered_mar_group.json", "w", encoding="utf-8") as f:
        json.dump(mar_group, f, ensure_ascii=False, indent=2)
    
    with open("staggered_apr_group.json", "w", encoding="utf-8") as f:
        json.dump(apr_group, f, ensure_ascii=False, indent=2)
    
    with open("staggered_control_group.json", "w", encoding="utf-8") as f:
        json.dump(control_group, f, ensure_ascii=False, indent=2)
    
    with open("staggered_all_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nFiles saved:")
    print(f"  staggered_jan_group.json ({len(jan_group)} games)")
    print(f"  staggered_feb_group.json ({len(feb_group)} games)")
    print(f"  staggered_mar_group.json ({len(mar_group)} games)")
    print(f"  staggered_apr_group.json ({len(apr_group)} games)")
    print(f"  staggered_control_group.json ({len(control_group)} games)")
    print(f"  staggered_all_results.json ({len(all_results)} total)")
    
    return {
        "jan_group": jan_group,
        "feb_group": feb_group,
        "mar_group": mar_group,
        "apr_group": apr_group,
        "control_group": control_group,
        "all_results": all_results
    }


if __name__ == "__main__":
    collect_staggered_groups(games_per_group=100, max_games_to_check=5000)
