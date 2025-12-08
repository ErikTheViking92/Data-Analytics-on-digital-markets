"""Collect panel data for staggered DiD around last major patch per game.

Workflow:
- Read a list of appids (from top30 results JSONs or a provided list).
- For each appid, use `patch_extractor.extract_patches_for_games` logic to get last major patch date.
  (We will import patch_extractor.extract_patches_for_games or call the function if provided.)
- Use `scraper.steamcharts_scraper.fetch_monthly_series` to get time series of player averages.
- For each game event, create rows for months t = -4..+4 relative to the event month (month of patch).
- Extract control variables: metacritic (from store data), owners_estimate (from steamdb), and recent review counts if available.
- Save `did_panel.csv` with columns: appid, name, event_month (YYYY-MM), rel_month (int -4..4), avg_players, peak_players, owners_estimate, metacritic, review_count, treatment (1/0), event_date

Notes:
- SteamCharts scraping is best-effort; missing months will be NaN.
- Review counts per month may not be available; script will leave them as NaN if not found.
"""

from typing import List, Dict, Optional
import os
import json
from datetime import datetime
import pandas as pd

from patch_extractor import extract_patches_for_games
from scraper.steamcharts_scraper import fetch_monthly_series
from scraper.store_scraper import SteamStoreScraper
from scraper.steamdb_scraper import SteamDBScraper
from scraper.cache import SteamCache


def read_appids_from_top_files() -> List[int]:
    files = ['top30_topsellers_results.json', 'top30_results.json']
    for fpath in files:
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [int(x.get('appid')) for x in data if x.get('appid')]
    return []


def extract_last_major_date(patch_summary: Dict, appid: int) -> Optional[datetime]:
    # patch_summary format from patch_extractor: summary[appid]['first_major_patch_date'] is string or None
    s = patch_summary.get(str(appid)) or patch_summary.get(appid)
    if not s:
        return None
    date_str = s.get('first_major_patch_date')
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except Exception:
            return None


def owners_from_steamdb(steamdb_data: Dict) -> Optional[float]:
    if not steamdb_data:
        return None
    owners = steamdb_data.get('owners')
    if not owners:
        return None
    if isinstance(owners, (int, float)):
        return float(owners)
    try:
        parts = str(owners).split('-')
        if len(parts) == 2:
            low = float(parts[0].replace(',', '').strip())
            high = float(parts[1].replace(',', '').strip())
            return (low + high) / 2.0
    except Exception:
        return None
    return None


def build_panel(appids: List[int], out_csv: str = 'did_panel.csv', use_cache: bool = True):
    cache = SteamCache() if use_cache else None
    store = SteamStoreScraper(cache=cache)
    steamdb = SteamDBScraper(cache=cache)

    # Extract patches for all apps via patch_extractor
    patch_out = extract_patches_for_games(appids, out_json='patches_past_year_for_panel.json')
    patch_summary = patch_out.get('summary', {})

    rows = []

    for appid in appids:
        print(f"Processing app {appid}...")
        # Store metadata
        try:
            store_data = store.fetch_app(appid)
        except Exception:
            store_data = None
        # SteamDB
        try:
            sdb = steamdb.fetch_app(appid)
        except Exception:
            sdb = None

        owners_est = owners_from_steamdb(sdb)
        metacritic = None
        if store_data:
            metacritic = store_data.get('metacritic')

        # Last major patch date
        last_major = extract_last_major_date(patch_summary, appid)
        if last_major is None:
            # No major patch -> still include control rows with event_date = NaT; treat as control
            # We'll still attempt to fetch series and set treatment=0
            treatment = 0
            event_dt = None
        else:
            treatment = 1
            event_dt = last_major

        # Fetch monthly series
        series = fetch_monthly_series(appid)
        # Convert series to DataFrame keyed by YYYY-MM
        df_series = pd.DataFrame(series)
        if df_series.empty:
            # create empty months with a consistent 'ym' column
            df_series = pd.DataFrame(columns=['date', 'avg', 'peak', 'ym'])
        else:
            # normalize date to YYYY-MM and ensure 'ym' exists
            df_series['date'] = pd.to_datetime(df_series['date'], errors='coerce')
            try:
                df_series['ym'] = df_series['date'].dt.to_period('M').dt.to_timestamp()
            except Exception:
                # fallback: create empty 'ym' column
                df_series['ym'] = pd.NaT
            try:
                if 'ym' in df_series.columns:
                    df_series = df_series.groupby('ym').agg({'avg':'mean','peak':'max'}).reset_index()
                else:
                    # keep as-is but ensure columns exist
                    df_series = df_series.assign(ym=pd.NaT)
            except Exception:
                # If grouping fails, keep original structure with ym column
                if 'ym' not in df_series.columns:
                    df_series['ym'] = pd.NaT

        # define event month
        if event_dt is not None:
            event_month = datetime(event_dt.year, event_dt.month, 1)
        else:
            event_month = None

        # For months -4..+4
        for rel in range(-4, 5):
            if event_month is None:
                # For control games, pick latest month available as reference and set rel months accordingly
                if df_series.empty or ('ym' in df_series.columns and df_series['ym'].isna().all()):
                    row_date = None
                    avg = None
                    peak = None
                else:
                    # If 'ym' column exists and is non-empty, use it; otherwise try to infer from 'date'
                    if 'ym' in df_series.columns and not df_series['ym'].isna().all():
                        latest = df_series['ym'].max()
                        row_date = latest + pd.DateOffset(months=rel)
                        matched = df_series[df_series['ym'] == row_date]
                    else:
                        # fallback: use 'date' column if present
                        if 'date' in df_series.columns and not df_series['date'].isna().all():
                            latest = pd.to_datetime(df_series['date']).max()
                            # normalize to start of month
                            latest_month = pd.Timestamp(year=latest.year, month=latest.month, day=1)
                            row_date = latest_month + pd.DateOffset(months=rel)
                            matched = df_series[pd.to_datetime(df_series['date']).dt.to_period('M').dt.to_timestamp() == row_date]
                        else:
                            row_date = None
                            matched = pd.DataFrame()
                    if not matched.empty:
                        avg = float(matched['avg'].iloc[0])
                        peak = float(matched['peak'].iloc[0])
                    else:
                        avg = None
                        peak = None
                event_date_str = None
            else:
                row_date = pd.Timestamp(event_month) + pd.DateOffset(months=rel)
                # find matching month in series
                matched = df_series[df_series['ym'] == row_date]
                if not matched.empty:
                    avg = float(matched['avg'].iloc[0])
                    peak = float(matched['peak'].iloc[0])
                else:
                    avg = None
                    peak = None
                event_date_str = event_month.strftime('%Y-%m-%d')

            rows.append({
                'appid': appid,
                'name': store_data.get('name') if store_data else None,
                'event_date': event_date_str,
                'rel_month': rel,
                'month': row_date.strftime('%Y-%m') if row_date is not None else None,
                'avg_players': avg,
                'peak_players': peak,
                'owners_estimate': owners_est,
                'metacritic_score': metacritic,
                'treatment': treatment
            })

    df_panel = pd.DataFrame(rows)
    df_panel.to_csv(out_csv, index=False)
    print(f"Wrote panel with {len(df_panel)} rows to {out_csv}")
    return df_panel


if __name__ == '__main__':
    appids = read_appids_from_top_files()
    if not appids:
        # fallback sample
        appids = [570, 730, 578080, 250820]
    panel = build_panel(appids[:30])
    print(panel.head())
