
import json
with open('plugins/pokemon_fr/font_map.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
with open('test_load.txt', 'w') as f:
    f.write(str(len(d)))

