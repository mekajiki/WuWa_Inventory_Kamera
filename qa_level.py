# レベル誤読(HPが高いのにLv低)や音骸欠落の検査
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open(sys.argv[1], encoding='utf-8'))
names = json.load(open(r'C:\Users\air_d\Documents\wuwa\names.json', encoding='utf-8'))['characters']
for k, v in d.items():
    hp = v.get('stats', {}).get('hp', 0)
    if hp > 8000 and (v['level'] < 40 or len(v.get('echoes', {})) < 5):
        print(f"{names.get(k, k)}: Lv{v['level']} asc{v['ascension']} hp={hp} echoes={len(v.get('echoes', {}))}")
