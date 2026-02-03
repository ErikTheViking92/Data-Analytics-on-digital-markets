from scraper.steamdb_scraper import SteamDBScraper

scraper = SteamDBScraper()

# Test CS2
print("Testing SteamDB player history for CS2 (730)...")
data = scraper.fetch_player_history(730)
print(f"Found {len(data)} data points")

if data:
    print("\nFirst 5 entries:")
    for entry in data[:5]:
        print(f"  {entry}")
    print("\nLast 5 entries:")
    for entry in data[-5:]:
        print(f"  {entry}")
else:
    print("No data found")
