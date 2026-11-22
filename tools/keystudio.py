# The drone's "It listens" on real music: the studio100 recordings (strings, wind, voices, piano;
# a human tempo; a room), each in its own key as music21 reads it from the score. The drone starts on
# another key; measured: how long until it is on the piece's key, the share of the time it is on it,
# the share of the time it at least sounds the right tonic, and its wrong moves. Modal and atonal
# music is left out (no key to follow).
#   SENS=0.6 (the slider), ONLY=<part of a name>, MOD=<another keyfollow.js to try>
import asyncio, json, os, sys
from playwright.async_api import async_playwright
from music21 import converter
NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
CAP = '/home/claude/omreval/cap100'; ST = '/home/claude/omreval/studio100'
SKIP = ('palestrina', 'trecento', 'monteverdi', 'josquin', 'luca', 'lusitano', 'ciconia', 'schoenberg', 'webern')
def truth(nm):
    k = converter.parse(f'{CAP}/{nm}.musicxml').analyze('key')
    return k.tonic.pitchClass, k.mode == 'minor', round(k.correlationCoefficient, 2)
async def main():
    sens = float(os.environ.get('SENS', '0.6')); only = os.environ.get('ONLY')
    cases = json.load(open('/home/claude/omreval/cap100.json'))
    names = [os.path.basename(c[0]).split('-p1')[0] for c in cases]
    names = [n for n in names if not n.startswith(SKIP) and os.path.exists(f'{ST}/{n}.wav') and (not only or only in n)]
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        if os.environ.get('MOD'): await pg.route('**/js/keyfollow.js', lambda r: r.fulfill(path=os.environ['MOD'], content_type='text/javascript'))
        await pg.route('**/__st100/**', lambda r: r.fulfill(path=f"{ST}/{r.request.url.split('/__st100/')[1]}", content_type='audio/wav'))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        T = {'n': 0, 'acc': 0, 'tonic': 0, 'wrong': 0, 'lat': [], 'never': 0}
        for nm in names:
            pc, minor, conf = truth(nm)
            if conf < 0.6: continue    # (a key music21 itself is unsure of)
            meta = json.load(open(f'{ST}/{nm}.json')); secs = meta['end'] + 1.5
            start = [(pc + 5) % 12, 0]
            ev = await pg.evaluate("(a) => window.__keyReal(a)", {'url': f'/__st100/{nm}.wav', 'secs': secs, 'key': start, 'sens': sens})
            ch = [(0.0, start[0], False)] + [(e[0], int(e[1].rstrip('m')), e[1].endswith('m')) for e in ev]
            def at(t):
                k = ch[0]
                for c in ch:
                    if c[0] <= t: k = c
                return k
            ok = tn = tot = 0; t = meta['lead'] + 1.0
            while t < secs - 1:
                k = at(t); tot += 1; ok += (k[1], k[2]) == (pc, minor); tn += k[1] == pc; t += 0.25
            hit = next((c[0] for c in ch if (c[1], c[2]) == (pc, minor)), None)
            lat = None if hit is None else round(hit - meta['lead'], 1)
            wrong = sum(1 for c in ch[1:] if (c[1], c[2]) != (pc, minor))
            T['n'] += 1; T['acc'] += ok / max(1, tot); T['tonic'] += tn / max(1, tot); T['wrong'] += wrong
            if lat is None: T['never'] += 1
            else: T['lat'].append(lat)
            print(f"{nm:34s} {NAMES[pc]}{'m' if minor else ''} ({conf})  on the key {ok / max(1, tot) * 100:5.1f}%  tonic {tn / max(1, tot) * 100:5.1f}%  found after {lat} s  wrong moves {wrong}  ({secs:.0f} s)", flush=True)
        L = sorted(T['lat'])
        print(f"\nTOTAL {T['n']} pieces: on the key {T['acc'] / max(1, T['n']) * 100:.1f}% of the time, on its tonic {T['tonic'] / max(1, T['n']) * 100:.1f}%  |  found in a median {L[len(L) // 2] if L else '-'} s, never in {T['never']}  |  wrong moves {T['wrong']} ({T['wrong'] / max(1, T['n']):.2f} a piece)")
        if errs: print('errors', errs[:2])
        await b.close()
asyncio.run(main())
