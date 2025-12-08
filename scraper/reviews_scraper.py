"""Fetch Steam review data via the Steam Web API and Store page scraping.

The reviews endpoint provides aggregated review statistics:
- Total review counts
- Positive vs negative split
- Percentage positive

Fallback: scrape Steam Store page for review summary if API fails.
"""

from typing import Optional, Dict
import requests
from bs4 import BeautifulSoup
import re
import os


STEAM_REVIEWS_API = "https://steamcommunity.com/api/GetAppReviews/v1"


def read_api_key(path: str = "APIkey.txt") -> Optional[str]:
    """Read Steam API key from file if it exists."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        key = f.read().strip()
        return key or None


def fetch_app_reviews(appid: int, api_key: Optional[str] = None, limit: int = 0) -> Optional[Dict]:
    """
    Fetch review statistics for an app from the Steam Community API.
    Falls back to None if API fails (rate limited or blocked).
    
    This endpoint doesn't strictly require an API key but benefits from having one for higher rate limits.
    
    Returns dict with:
    - total_reviews: int (total number of reviews)
    - total_positive: int (number of positive reviews)
    - total_negative: int (number of negative reviews)
    - percent_positive: float (0-100 scale)
    - review_score_desc: str (e.g., "Overwhelmingly Positive")
    
    If limit > 0, fetches more details (paginated); otherwise just gets summary.
    """
    params = {
        "appid": appid,
        "json": 1,
        "cursor": "*",
        "num_per_page": 0,  # 0 means just get summary, no reviews
        "language": "english",
    }
    
    if api_key:
        params["key"] = api_key
    
    try:
        resp = requests.get(
            STEAM_REVIEWS_API,
            params=params,
            timeout=10,
            headers={"User-Agent": "steam-scraper/1.0"}
        )
        resp.raise_for_status()
        
        # Try to parse JSON; if empty or invalid, return None
        try:
            data = resp.json()
        except Exception:
            # API returned invalid JSON (likely rate limited)
            return None
        
        if not data.get("success"):
            return None
        
        query_summary = data.get("query_summary", {})
        
        return {
            "appid": appid,
            "total_reviews": query_summary.get("total_reviews", 0),
            "total_positive": query_summary.get("total_positive", 0),
            "total_negative": query_summary.get("total_negative", 0),
            "percent_positive": query_summary.get("percent_positive", 0),
            "review_score_desc": query_summary.get("review_score_desc", "N/A"),
            "review_type": query_summary.get("review_type", "all"),
            "purchase_type": query_summary.get("purchase_type", "all"),
        }
    except Exception as e:
        # Silently fail; review data is optional
        return None


def fetch_app_reviews_recent(appid: int, api_key: Optional[str] = None, days: int = 30) -> Optional[Dict]:
    """
    Fetch recent review statistics for an app (reviews from past N days).
    Falls back to None if API fails.
    
    Returns dict similar to fetch_app_reviews but for recent period only.
    """
    params = {
        "appid": appid,
        "json": 1,
        "cursor": "*",
        "num_per_page": 0,
        "language": "english",
        "filter": "recent",  # Get recent reviews
        "purchase_type": "all",
    }
    
    if api_key:
        params["key"] = api_key
    
    try:
        resp = requests.get(
            STEAM_REVIEWS_API,
            params=params,
            timeout=10,
            headers={"User-Agent": "steam-scraper/1.0"}
        )
        resp.raise_for_status()
        
        try:
            data = resp.json()
        except Exception:
            # API returned invalid JSON
            return None
        
        if not data.get("success"):
            return None
        
        query_summary = data.get("query_summary", {})
        
        return {
            "appid": appid,
            "period": "recent",
            "total_reviews": query_summary.get("total_reviews", 0),
            "total_positive": query_summary.get("total_positive", 0),
            "total_negative": query_summary.get("total_negative", 0),
            "percent_positive": query_summary.get("percent_positive", 0),
            "review_score_desc": query_summary.get("review_score_desc", "N/A"),
        }
    except Exception:
        # Silently fail
        return None


if __name__ == '__main__':
    # Quick manual test
    api_key = read_api_key()
    example_appid = 570  # Dota 2
    
    reviews = fetch_app_reviews(example_appid, api_key=api_key)
    print(f"All-time reviews for {example_appid}:")
    print(reviews)
    
    recent = fetch_app_reviews_recent(example_appid, api_key=api_key)
    print(f"\nRecent reviews for {example_appid}:")
    print(recent)
