"""Scrape top Steam games to find:
1. 100 games with major patches in February 2025
2. 100 games without major patches in February 2025

Treatment timepoint: mid-February 2025 (February 15, 2025)
Timeframe: Two weeks before and after (February 1-28, 2025)

Outputs:
- february_2025_treatment_group.json: 100 games with major patches
- february_2025_control_group.json: 100 games without major patches
- february_2025_all_results.json: All processed games
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from scraper.store_scraper import SteamStoreScraper
from scraper.steamdb_scraper import SteamDBScraper
from scraper.cache import SteamCache


STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
STEAM_PLAYERCOUNT_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"

# February 2025 timeframe
FEBRUARY_START = datetime(2025, 2, 1)
FEBRUARY_END = datetime(2025, 2, 28, 23, 59, 59)
TREATMENT_TIMEPOINT = datetime(2025, 2, 15)


def read_api_key(path: str = "APIkey.txt") -> Optional[str]:
    """Read Steam API key from file if it exists."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        key = f.read().strip()
        return key or None


def fetch_top_most_played(n: int = 100, start: int = 0) -> List[dict]:
    """Fetch top games from Steam Store search sorted by popular (most played).
    
    Args:
        n: Number of games to fetch
        start: Starting position (for pagination)
    """
    url = "https://store.steampowered.com/search/"
    params = {
        "os": "win",
        "sort_by": "popular",
        "count": min(n, 100),  # Steam API limit is 100 per request
        "start": start,
    }
    resp = requests.get(
        url,
        params=params,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
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
    """Fetch news items for an app from Steam Web API."""
    params = {
        "appid": appid,
        "count": count,
        "maxlength": 2000
    }
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
    """Fetch current player count for an app."""
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
    """
    Classify if a news item is a major patch.
    
    Returns: (is_major_patch: bool, reason: str or None)
    """
    combined = (title + " " + contents).lower()
    
    # Check if it's patch-related at all
    patch_keywords = [
        "patch", "update", "hotfix", "fix", "bug", "balance", 
        "expansion", "dlc", "content update", "new feature",
        "maintenance", "adjustment", "tweak", "improvement"
    ]
    is_patch = any(kw in combined for kw in patch_keywords)
    
    if not is_patch:
        return (False, None)
    
    # UPDATED KEYWORDS: More specific major patch indicators
    major_indicators = [
        "major update", "major patch", "big update", "massive update",
        "expansion", "new expansion", "dlc",
        "content update", "content patch",
        "new game mode", "new map", "new maps",
        "new character", "new characters", "new weapon", "new weapons",
        "gameplay change", "gameplay update", "mechanic change", "mechanics update",
        "overhaul", "rework", "redesign",
        "substantial", "significant", "massive",
        "season", "new season", "battle pass",
        "complete rework", "major rework", "major overhaul",
        "major release", "major content"
    ]
    
    # Minor patch indicators (explicitly NOT major)
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
    
    # Classification logic
    if is_minor_candidate and not is_major_candidate:
        return (False, "minor_keywords")
    elif is_major_candidate:
        return (True, "major_keywords")
    else:
        # Default: treat generic "update" or "patch" as MINOR unless explicitly major
        # This is more conservative - we only count clear major patches
        if "bug fix" in combined or "hotfix" in combined or "balance" in combined:
            return (False, "default_minor")
        elif "update" in combined and "content" not in combined:
            return (False, "generic_update")
        else:
            # If it's a patch but unclear, default to minor
            return (False, "unclear_patch")


def has_major_patch_in_february(appid: int, api_key: Optional[str] = None) -> tuple[bool, List[dict]]:
    """
    Check if a game has major patches in February 2025.
    
    Returns: (has_major_patch: bool, february_major_patches: List[dict])
    """
    news = fetch_news_for_app(appid, api_key=api_key, count=100)
    
    february_major_patches = []
    
    for item in news:
        unix_ts = item.get("date", 0)
        try:
            item_date = datetime.utcfromtimestamp(unix_ts)
        except Exception:
            continue
        
        # Check if in February 2025
        if not (FEBRUARY_START <= item_date <= FEBRUARY_END):
            continue
        
        title = item.get("title", "")
        contents = item.get("contents", "")
        
        is_major, reason = classify_major_patch(title, contents)
        
        if is_major:
            february_major_patches.append({
                "title": title,
                "contents": contents[:500],
                "date": item_date.strftime("%Y-%m-%d %H:%M:%S"),
                "unix_timestamp": unix_ts,
                "classification_reason": reason
            })
    
    return (len(february_major_patches) > 0, february_major_patches)


def collect_february_2025_groups(
    target_treatment: int = 100,
    target_control: int = 100,
    max_games_to_check: int = 1000,
    use_cache: bool = True
):
    """
    Collect treatment and control groups for February 2025 analysis.
    
    Args:
        target_treatment: Number of treatment games to collect (with major patches)
        target_control: Number of control games to collect (without major patches)
        max_games_to_check: Maximum number of games to check
        use_cache: Whether to use cache
    """
    api_key = read_api_key()
    print(f"Using API key: {'present' if api_key else 'none'}")
    print(f"Target: {target_treatment} treatment + {target_control} control games")
    print(f"February 2025 timeframe: {FEBRUARY_START.date()} to {FEBRUARY_END.date()}")
    print(f"Treatment timepoint: {TREATMENT_TIMEPOINT.date()}\n")

    cache = SteamCache() if use_cache else None
    if cache:
        stats = cache.get_stats()
        print(f"Cache: {stats['total']} entries\n")

    store = SteamStoreScraper(cache=cache)
    steamdb = SteamDBScraper(cache=cache)

    treatment_group = []
    control_group = []
    all_results = []
    
    games_checked = 0
    start_position = 0
    
    while (len(treatment_group) < target_treatment or len(control_group) < target_control) and games_checked < max_games_to_check:
        # Fetch next batch of top games
        batch = fetch_top_most_played(n=100, start=start_position)
        if not batch:
            print(f"\nNo more games to fetch at position {start_position}")
            break
        
        print(f"\nFetched {len(batch)} games (starting at position {start_position})")
        start_position += len(batch)
        
        for item in batch:
            if len(treatment_group) >= target_treatment and len(control_group) >= target_control:
                break
            
            aid = item["appid"]
            name = item.get("name")
            games_checked += 1
            
            print(f"[{games_checked}] Processing {aid} - {name}")
            
            # Check for major patches in February
            has_patch, patches = has_major_patch_in_february(aid, api_key=api_key)
            
            # Create entry
            entry = {
                "appid": aid,
                "name": name,
                "collected_at": datetime.utcnow().isoformat(),
                "has_major_patch_feb2025": has_patch,
                "february_major_patches": patches,
                "february_major_patch_count": len(patches)
            }
            
            # Fetch store metadata
            try:
                entry["store"] = store.fetch_app(aid)
            except Exception as e:
                entry["store"] = None
                entry["store_error"] = str(e)
            
            # Fetch SteamDB data
            try:
                entry["steamdb"] = steamdb.fetch_app(aid)
            except Exception as e:
                entry["steamdb"] = None
                entry["steamdb_error"] = str(e)
            
            # Fetch current players
            try:
                entry["current_players"] = fetch_current_players(aid)
            except Exception:
                entry["current_players"] = None
            
            all_results.append(entry)
            
            # Assign to groups
            if has_patch and len(treatment_group) < target_treatment:
                treatment_group.append(entry)
                print(f"  -> TREATMENT group (#{len(treatment_group)}): {len(patches)} major patches in Feb 2025")
            elif not has_patch and len(control_group) < target_control:
                control_group.append(entry)
                print(f"  -> CONTROL group (#{len(control_group)}): No major patches in Feb 2025")
            else:
                print(f"  -> Skipped (groups full or wrong type)")
            
            print(f"  Progress: Treatment {len(treatment_group)}/{target_treatment}, Control {len(control_group)}/{target_control}")
    
    # Save results
    print(f"\n{'='*60}")
    print(f"Collection complete!")
    print(f"Treatment group: {len(treatment_group)} games")
    print(f"Control group: {len(control_group)} games")
    print(f"Total games checked: {games_checked}")
    
    with open("february_2025_treatment_group.json", "w", encoding="utf-8") as f:
        json.dump(treatment_group, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(treatment_group)} games to february_2025_treatment_group.json")
    
    with open("february_2025_control_group.json", "w", encoding="utf-8") as f:
        json.dump(control_group, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(control_group)} games to february_2025_control_group.json")
    
    with open("february_2025_all_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(all_results)} total games to february_2025_all_results.json")
    
    # Print sample from treatment group
    print(f"\n{'='*60}")
    print("Sample from Treatment Group (first 5 games):")
    for i, game in enumerate(treatment_group[:5], 1):
        print(f"\n{i}. {game['name']} (AppID: {game['appid']})")
        print(f"   Major patches in Feb 2025: {game['february_major_patch_count']}")
        for patch in game['february_major_patches'][:2]:
            print(f"   - {patch['date']}: {patch['title'][:60]}...")
    
    return {
        "treatment_group": treatment_group,
        "control_group": control_group,
        "all_results": all_results
    }


if __name__ == "__main__":
    collect_february_2025_groups(
        target_treatment=100,
        target_control=100,
        max_games_to_check=1000
    )
