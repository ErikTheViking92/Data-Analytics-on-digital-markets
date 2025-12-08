"""Extract and classify major patches from Steam game news for the past year.

Workflow:
- Fetches news for each game using Steam Web API ISteamNews/GetNewsForApp/v2
- Extracts patch/update articles with exact dates
- Classifies patches as MAJOR or MINOR based on keywords and heuristics
- Outputs to JSON with game-level patch summary and detailed patch records

Major patch indicators:
- Keywords: "major update", "major patch", "expansion", "content update", "new feature"
- Gameplay/mechanical changes (not cosmetic)
- Large version bumps (e.g., 1.0 -> 2.0, 2.1 -> 2.5)

Minor patch indicators:
- Keywords: "hotfix", "bug fix", "performance", "balance", "cosmetic"
- Small adjustments to existing features
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import os


STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
NEWS_FETCH_COUNT = 100  # Fetch more news to catch all patches


def read_api_key(path: str = "APIkey.txt") -> Optional[str]:
    """Read Steam API key from file if it exists."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        key = f.read().strip()
        return key or None


def fetch_news_for_app(appid: int, api_key: Optional[str] = None, count: int = 100) -> List[Dict]:
    """Fetch news items for an app from Steam Web API."""
    params = {
        "appid": appid,
        "count": count,
        "maxlength": 2000  # Allow longer content to analyze
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


def classify_patch(title: str, contents: str) -> Optional[tuple]:
    """
    Classify a news item as a patch and determine if MAJOR or MINOR.
    Returns: (is_patch: bool, is_major: bool, classification_reason: str)
    """
    combined = (title + " " + contents).lower()
    
    # Check if it's patch-related
    patch_keywords = [
        "patch", "update", "hotfix", "fix", "bug", "balance", 
        "expansion", "dlc", "content update", "new feature",
        "maintenance", "adjustment", "tweak", "improvement"
    ]
    is_patch = any(kw in combined for kw in patch_keywords)
    
    if not is_patch:
        return None
    
    # Classify as MAJOR or MINOR
    major_indicators = [
        "major update", "major patch", "expansion", "new content",
        "new feature", "new game mode", "new map", "new character",
        "gameplay change", "mechanic change", "overhaul",
        "substantial", "significant", "massive", "complete rework"
    ]
    
    minor_indicators = [
        "hotfix", "bug fix", "small fix", "minor", "performance",
        "cosmetic", "visual", "balance adjustment", "tweak",
        "adjustment", "stability"
    ]
    
    is_major_candidate = any(ind in combined for ind in major_indicators)
    is_minor_candidate = any(ind in combined for ind in minor_indicators)
    
    # Logic: if explicitly marked minor, it's minor
    # if no indicators or only major indicators, it's major
    # if only minor indicators, it's minor
    if is_minor_candidate and not is_major_candidate:
        is_major = False
        reason = "minor_keywords"
    elif is_major_candidate:
        is_major = True
        reason = "major_keywords"
    else:
        # Default: treat generic "update" as MAJOR (likely content-related)
        # but "hotfix" and "bug fix" as MINOR
        if "bug fix" in combined or "hotfix" in combined:
            is_major = False
            reason = "default_minor"
        else:
            is_major = True
            reason = "default_major"
    
    return (True, is_major, reason)


def extract_patches_for_games(appids: List[int], out_json: str = "patches_past_year.json") -> Dict:
    """
    Extract patches for a list of game appids from the past year.
    
    Returns dict:
    {
        "summary": {
            "<appid>": {
                "name": "...",
                "total_patches": int,
                "major_patches": int,
                "minor_patches": int,
                "has_major_patch": bool,  # Treatment group indicator
                "first_major_patch_date": "YYYY-MM-DD" or None,
                "last_patch_date": "YYYY-MM-DD" or None
            }
        },
        "patches": [
            {
                "appid": int,
                "title": str,
                "contents": str,
                "date": "YYYY-MM-DD HH:MM:SS",
                "unix_timestamp": int,
                "is_major": bool,
                "classification_reason": str
            }
        ]
    }
    """
    api_key = read_api_key()
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    
    print(f"Extracting patches from {len(appids)} games (past year: since {one_year_ago.date()})")
    print(f"Using API key: {'present' if api_key else 'none'}\n")
    
    summary = {}
    all_patches = []
    
    for appid in appids:
        print(f"Processing appid {appid}...")
        
        # Fetch news
        news = fetch_news_for_app(appid, api_key=api_key, count=NEWS_FETCH_COUNT)
        
        patches = []
        for item in news:
            # Check timestamp
            unix_ts = item.get("date", 0)
            try:
                item_date = datetime.utcfromtimestamp(unix_ts)
            except Exception:
                continue
            
            if item_date < one_year_ago:
                continue  # Older than 1 year
            
            title = item.get("title", "")
            contents = item.get("contents", "")
            
            # Classify
            classification = classify_patch(title, contents)
            if not classification:
                continue  # Not a patch
            
            is_patch, is_major, reason = classification
            
            patch_entry = {
                "appid": appid,
                "title": title,
                "contents": contents[:500],  # Truncate for size
                "date": item_date.strftime("%Y-%m-%d %H:%M:%S"),
                "unix_timestamp": unix_ts,
                "is_major": is_major,
                "classification_reason": reason
            }
            patches.append(patch_entry)
            all_patches.append(patch_entry)
        
        # Summarize
        major_count = sum(1 for p in patches if p["is_major"])
        minor_count = len(patches) - major_count
        
        last_patch_date = None
        first_major_patch_date = None
        
        if patches:
            last_patch_date = max(p["date"] for p in patches)
        if any(p["is_major"] for p in patches):
            major_patches = [p for p in patches if p["is_major"]]
            first_major_patch_date = min(p["date"] for p in major_patches)
        
        summary[appid] = {
            "total_patches": len(patches),
            "major_patches": major_count,
            "minor_patches": minor_count,
            "has_major_patch": major_count > 0,
            "first_major_patch_date": first_major_patch_date,
            "last_patch_date": last_patch_date
        }
        
        print(f"  -> {len(patches)} patches ({major_count} major, {minor_count} minor)")
    
    output = {
        "extraction_date": datetime.utcnow().isoformat(),
        "period": "past 365 days",
        "summary": summary,
        "patches": all_patches
    }
    
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nWrote {len(all_patches)} patches to {out_json}")
    return output


if __name__ == "__main__":
    # Example: extract patches for top 30 games
    # You can provide a list of appids here
    sample_appids = [570, 730, 251570, 275850, 578080, 489830, 363970, 431960, 583950]
    result = extract_patches_for_games(sample_appids)
    
    print("\n=== Summary ===")
    for appid, summary in result["summary"].items():
        print(f"AppID {appid}: {summary['major_patches']} major, {summary['minor_patches']} minor")
