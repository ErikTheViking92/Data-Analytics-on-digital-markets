import json
from scraper.steamcharts_scraper import fetch_monthly_series

# Load all game groups
with open('staggered_jan_group.json', encoding='utf-8') as f:
    jan_games = json.load(f)

print(f"Testing why games were excluded...")
print(f"Total games in Jan group: {len(jan_games)}")

target_months = ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04']

# Test first 20 games
games_with_data = 0
games_without_data = 0

print("\nTesting first 20 games:")
for i, game in enumerate(jan_games[:20]):
    appid = game['appid']
    name = game.get('name', 'Unknown')[:40]
    
    data = fetch_monthly_series(appid)
    
    # Check if we have all target months
    has_all = all(any(d.get('date', '').startswith(month) for d in data) 
                  for month in target_months)
    
    if has_all:
        games_with_data += 1
        status = "✓ INCLUDED"
    else:
        games_without_data += 1
        status = "✗ EXCLUDED"
        # Show which months are missing
        missing = [m for m in target_months 
                  if not any(d.get('date', '').startswith(m) for d in data)]
        print(f"  {i+1}. {appid} ({name}): {status}")
        print(f"      Total data points: {len(data)}, Missing months: {missing}")

print(f"\nSummary for first 20 games:")
print(f"  With complete data: {games_with_data}")
print(f"  Without complete data: {games_without_data}")

# Check if it's an issue with the current scraper or game availability
print("\nChecking a few excluded games in detail...")
for game in jan_games[:30]:
    appid = game['appid']
    data = fetch_monthly_series(appid)
    has_all = all(any(d.get('date', '').startswith(month) for d in data) 
                  for month in target_months)
    if not has_all and len(data) > 0:
        print(f"\nGame {appid}: Has {len(data)} points but missing some target months")
        print(f"  Available months: {[d['date'][:7] for d in data if '2024-12' <= d['date'] <= '2025-05']}")
        break
