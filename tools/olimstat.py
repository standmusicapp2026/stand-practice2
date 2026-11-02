import json, sys
from collections import Counter
r = json.load(open(sys.argv[1]))
CL = {'treble': 'G2', 'bass': 'F4', 'alto': 'C3', 'tenor': 'C4'}
groups = {}
for x in r:
    for i, s in enumerate(x['staves']):
        k = ('keyOK' if s['key'] == s['gtKey'] else 'keyBAD') + '/' + ('clefOK' if CL.get(s['clef']) == s['gtClef'] else 'clefBAD')
        g = groups.setdefault(k, [0, 0, 0, 0]); g[0] += 1; g[1] += s['gt']; g[2] += s['pitch']; g[3] += s['rhythm']
for k, g in sorted(groups.items()): print(k, 'staves', g[0], 'onsets', g[1], f'pitch {g[2]/max(1,g[1])*100:.1f}% rhythm {g[3]/max(1,g[1])*100:.1f}%')
print('key confusions', Counter((s['gtKey'], s['key']) for x in r for s in x['staves'] if s['key'] != s['gtKey']).most_common(15))
print('clef confusions', Counter((s['gtClef'], s['clef']) for x in r for s in x['staves'] if CL.get(s['clef']) != s['gtClef']).most_common(10))
