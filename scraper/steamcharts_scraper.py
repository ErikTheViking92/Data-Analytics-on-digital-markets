"""Best-effort SteamCharts scraper to obtain historical monthly average and peak players for an app.

The SteamCharts site structure can change. This module attempts multiple parsing strategies:
- Look for embedded JSON arrays in the page (common pattern: chart data embedded in script)
- Fall back to parsing HTML tables if present

Functions:
- fetch_monthly_series(appid): returns a list of dicts {date, avg, peak}

Note: This is best-effort scraping. If SteamCharts blocks or changes layout, results may be incomplete.
"""
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

HEADERS = {"User-Agent": "steam-scraper/1.0 (+https://github.com)"}


def _parse_chartdata_json(text: str) -> Optional[List[Dict]]:
    """Try to extract a JavaScript JSON array that contains chart data.
    Several patterns are possible; attempt a few common ones.
    Returns list of [timestamp_ms, avg, peak] or similar.
    """
    # Pattern: var chartData = ...; or chartData = [...];
    m = re.search(r"chartData\s*=\s*(\[.+?\])\s*;", text, flags=re.S)
    if not m:
        # Try another pattern: series: [{data: [...] }]
        m = re.search(r"data:\s*(\[\[.*?\]\])\s*\}", text, flags=re.S)
    if not m:
        # Try JSON-like assignment: g.setData( ... );
        m = re.search(r"setData\((\[.+?\])\)", text, flags=re.S)
    if not m:
        return None
    try:
        arr_text = m.group(1)
        # Clean up trailing commas
        arr_text = re.sub(r",\s*\]", "]", arr_text)
        data = json.loads(arr_text)
        # Data may be list of [ts, avg, peak] or dicts
        return data
    except Exception:
        return None


def fetch_monthly_series(appid: int) -> List[Dict]:
    """Fetch monthly series from SteamCharts.

    Returns list of dicts: {date: 'YYYY-MM', avg: float, peak: float}
    """
    url = f"https://steamcharts.com/app/{appid}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print(f"  [steamcharts] Error fetching app {appid}: {e}")
        return []

    # Attempt to parse embedded JSON
    parsed = _parse_chartdata_json(text)
    results = []
    if parsed:
        # parsed could be list of [ts, avg, peak]
        for item in parsed:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            try:
                ts = int(item[0])
                # ts may be in milliseconds
                if ts > 1e12:
                    # milliseconds
                    dt = datetime.utcfromtimestamp(ts / 1000.0)
                else:
                    dt = datetime.utcfromtimestamp(ts)
                avg = float(item[1]) if item[1] is not None else None
                peak = float(item[2]) if item[2] is not None else None
                results.append({"date": dt.strftime("%Y-%m-%d"), "avg": avg, "peak": peak})
            except Exception:
                continue
        if results:
            return results

    # Fallback: try to parse HTML table rows for monthly data
    try:
        soup = BeautifulSoup(text, 'lxml')
        # Look for a table with class that suggests monthly data
        tables = soup.find_all('table')
        for table in tables:
            # Heuristic: table contains 'Month' header or 'Average players' text
            header = table.get_text().lower()
            if 'month' in header or 'average' in header:
                for tr in table.find_all('tr'):
                    cols = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if len(cols) >= 3:
                        # Try parse date and numbers
                        try:
                            # Find a YYYY or Month Year in cols[0]
                            date_str = cols[0]
                            # Attempt to parse month-year
                            try:
                                dt = datetime.strptime(date_str.strip(), '%B %Y')
                                date_key = dt.strftime('%Y-%m-01')
                            except Exception:
                                date_key = date_str
                            avg = float(cols[1].replace(',', '').replace('–', '0') or 0)
                            peak = float(cols[2].replace(',', '').replace('–', '0') or 0)
                            results.append({"date": date_key, "avg": avg, "peak": peak})
                        except Exception:
                            continue
                if results:
                    return results
    except Exception:
        pass

    # If still nothing, attempt to parse any JSON arrays in the page
    try:
        json_arrays = re.findall(r"(\[\s*\[\s*\d+\s*,\s*\d+.*?\])", text, flags=re.S)
        for arr_text in json_arrays:
            try:
                arr = json.loads(arr_text)
                for item in arr:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        ts = int(item[0])
                        if ts > 1e12:
                            dt = datetime.utcfromtimestamp(ts / 1000.0)
                        else:
                            dt = datetime.utcfromtimestamp(ts)
                        avg = float(item[1])
                        peak = float(item[2])
                        results.append({"date": dt.strftime('%Y-%m-%d'), "avg": avg, "peak": peak})
                if results:
                    return results
            except Exception:
                continue
    except Exception:
        pass

    # No data found
    return []


if __name__ == '__main__':
    # Quick manual test example (won't run in CI automatically)
    example_appid = 570
    series = fetch_monthly_series(example_appid)
    print(f"Found {len(series)} data points for {example_appid}")
    for r in series[:10]:
        print(r)
