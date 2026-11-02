import json, sys
a = {x['id']: x for x in json.load(open(sys.argv[1]))}; b = {x['id']: x for x in json.load(open(sys.argv[2]))}
rows = []
for k in a:
    if k not in b: continue
    for i in (0, 1):
        sa, sb = a[k]['staves'][i], b[k]['staves'][i]
        rows.append((sb['pitch'] - sa['pitch'], k, i, sa['pitch'], sb['pitch'], sa['gt'], sa['key'], sb['key'], sa['gtKey'], sa['clef'], sb['clef']))
rows.sort()
for r in rows[:12]: print('WORSE', r)
for r in rows[-12:]: print('BETTER', r)
print('sum', sum(r[0] for r in rows))
