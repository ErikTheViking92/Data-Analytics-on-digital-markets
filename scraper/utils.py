import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def create_session(retries: int = 3, backoff_factor: float = 0.3, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "steam-scraper/1.0 (+https://github.com/)"})
    return session


class RateLimiter:
    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self):
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


def safe_get(session: requests.Session, url: str, rate_limiter: RateLimiter = None, **kwargs):
    if rate_limiter:
        rate_limiter.wait()
    resp = session.get(url, **kwargs)
    resp.raise_for_status()
    return resp
