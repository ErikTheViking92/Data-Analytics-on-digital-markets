from scraper.steamcharts_scraper import fetch_monthly_series
import json

# Test a few games to see what data we get
test_apps = [730, 570, 1245620, 252490]  # CS2, Dota 2, Elden Ring, Rust

for appid in test_apps:
    print(f"\n{'='*80}")
    print(f"Testing AppID {appid}")
    print('='*80)
    
    data = fetch_monthly_series(appid)
    print(f"Total data points returned: {len(data)}")
    
    if data:
        print("\nFirst 10 entries:")
        for entry in data[:10]:
            print(f"  {entry}")
        
        print("\nLast 10 entries:")
        for entry in data[-10:]:
            print(f"  {entry}")
        
        # Check for our target months
        target_months = ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04']
        print(f"\nChecking for target months (Dec 2024 - Apr 2025):")
        for month in target_months:
            matching = [d for d in data if d.get('date', '').startswith(month)]
            if matching:
                print(f"  {month}: Found {len(matching)} entries - {matching[0]}")
            else:
                print(f"  {month}: NOT FOUND")
    else:
        print("NO DATA RETURNED")
