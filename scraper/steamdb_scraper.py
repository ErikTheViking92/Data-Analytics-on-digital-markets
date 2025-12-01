import re
import time
import random
from typing import Optional
from bs4 import BeautifulSoup
from .utils import create_session, RateLimiter
from .cache import SteamCache


class SteamDBScraper:
    """More robust SteamDB scraper with stronger headers, randomized delays,
    backoff on 403 responses, and optional proxy support.

    Warning: SteamDB is a third-party site and may block scraping. Use caching
    and respect `robots.txt` and the site's terms.
    """

    BASE_URL = "https://steamdb.info/app/{appid}/"

    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    ]

    def __init__(self, rate_limit_seconds: float = 1.0, proxies: Optional[dict] = None, max_403_retries: int = 3, cache: Optional[SteamCache] = None):
        self.session = create_session()
        self.rate_limiter = RateLimiter(rate_limit_seconds)
        self.proxies = proxies
        self.max_403_retries = max_403_retries
        self.cache = cache or SteamCache()

        # sensible default headers
        self.session.headers.update({
            "User-Agent": random.choice(self.DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://steamcommunity.com/",
            "Origin": "https://steamdb.info",
        })

    def _get_html(self, url: str) -> Optional[str]:
        # Rate-limit
        self.rate_limiter.wait()

        backoff = 1.0
        tries = 0
        while tries <= self.max_403_retries:
            tries += 1
            # rotate UA occasionally
            if tries > 1:
                self.session.headers["User-Agent"] = random.choice(self.DEFAULT_USER_AGENTS)

            try:
                resp = self.session.get(url, timeout=15, proxies=self.proxies)
                if resp.status_code == 403:
                    # exponential backoff
                    time.sleep(backoff + random.random() * 0.5)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                # small randomized delay to look less like a bot
                time.sleep(0.2 + random.random() * 0.6)
                return resp.text
            except Exception:
                # brief sleep and retry
                time.sleep(backoff)
                backoff = min(backoff * 2, 8)
                continue
        return None

    def _find_label_value(self, soup, label_regex: str):
        # Find nodes with label text then read nearby text
        pattern = re.compile(label_regex, re.I)
        for tag in soup.find_all(text=pattern):
            parent = tag.parent
            # look for sibling or next element text
            sib = parent.find_next_sibling()
            if sib and sib.get_text(strip=True):
                return sib.get_text(strip=True)
            # else try parent.parent
            if parent.parent:
                nxt = parent.parent.find_next_sibling()
                if nxt and nxt.get_text(strip=True):
                    return nxt.get_text(strip=True)
        return None

    def fetch_app(self, appid: int) -> Optional[dict]:
        # Check cache first
        cached = self.cache.get("steamdb_app", appid)
        if cached is not None:
            return cached
        
        url = self.BASE_URL.format(appid=appid)
        html = self._get_html(url)
        if not html:
            return {"appid": appid, "steamdb_url": url, "owners": None, "peak_players": None, "raw_html_snippet": None}

        soup = BeautifulSoup(html, "lxml")

        # Try to extract owners; SteamDB often shows owners estimates in textual form
        owners = self._find_label_value(soup, r"Owners|Owned")
        peak_players = self._find_label_value(soup, r"Peak\s*players")

        # As a fallback, attempt regex search in raw HTML for patterns like 1,234,567
        if not owners:
            m = re.search(r"Owners[:\s]*([\d,]+)", html)
            if m:
                owners = m.group(1)

        if not peak_players:
            m = re.search(r"Peak players[:\s]*([\d,]+)", html)
            if m:
                peak_players = m.group(1)

        result = {
            "appid": appid,
            "steamdb_url": url,
            "owners": owners,
            "peak_players": peak_players,
            "raw_html_snippet": html[:800] if html else None,
        }
        # Cache the result
        if result:
            self.cache.set("steamdb_app", appid, result)
        return result
