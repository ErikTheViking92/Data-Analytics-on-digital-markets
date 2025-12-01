import json
from typing import Optional
from .utils import create_session, RateLimiter, safe_get
from .cache import SteamCache


class SteamStoreScraper:
    """Fetches metadata from the official Steam Store API endpoint.

    Uses the public `appdetails` endpoint which returns structured JSON for an appid.
    This is preferable to parsing HTML where possible.
    """

    API_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(self, rate_limit_seconds: float = 0.5, cache: Optional[SteamCache] = None):
        self.session = create_session()
        self.rate_limiter = RateLimiter(rate_limit_seconds)
        self.cache = cache or SteamCache()

    def fetch_app(self, appid: int) -> Optional[dict]:
        # Check cache first
        cached = self.cache.get("store_appdetails", appid)
        if cached is not None:
            return cached
        
        params = {"appids": str(appid), "l": "english"}
        resp = safe_get(self.session, self.API_URL, rate_limiter=self.rate_limiter, params=params, timeout=15)
        data = resp.json()
        if not data or str(appid) not in data or not data[str(appid)].get("success"):
            return None
        raw = data[str(appid)].get("data", {})

        # Normalize fields we commonly want
        result = {
            "appid": appid,
            "name": raw.get("name"),
            "type": raw.get("type"),
            "short_description": raw.get("short_description"),
            "detailed_description": raw.get("detailed_description"),
            "developers": raw.get("developers", []),
            "publishers": raw.get("publishers", []),
            "release_date": raw.get("release_date", {}).get("date"),
            "platforms": raw.get("platforms", {}),
            "categories": [c.get("description") for c in raw.get("categories", [])],
            "genres": [g.get("description") for g in raw.get("genres", [])],
            "price_overview": raw.get("price_overview"),
            "metacritic": raw.get("metacritic"),
            "header_image": raw.get("header_image"),
            "screenshots": raw.get("screenshots", []),
            "release_raw": raw,
        }
        # Cache the result
        if result:
            self.cache.set("store_appdetails", appid, result)
        return result
