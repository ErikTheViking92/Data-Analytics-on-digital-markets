import json

# Load control group
with open('staggered_control_group.json', 'r', encoding='utf-8') as f:
    control_data = json.load(f)

print(f'Total control games: {len(control_data)}')

# Check for December patches
dec_games = [g for g in control_data if g.get('dec_count', 0) > 0]
print(f'Games with Dec 2024 patches: {len(dec_games)}')

if dec_games:
    print('\nGames with Dec patches:')
    for g in dec_games[:20]:  # Show up to 20
        print(f"  {g['name']} - {g['dec_count']} patches")
