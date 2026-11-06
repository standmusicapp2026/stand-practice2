# Holst, Jupiter: the Andante maestoso (the big tune), as in the Boosey & Hawkes full score
# (B.& H. 15970, pp. 91-94): the melody, its octaves, who plays it when, the dynamics, slurs,
# "non legato", pizz./arco, the solo trumpet, rehearsal IX and the ff tutti, written out for Stand's
# Compose (concert pitch). Accompanying chords follow the score's harmony in simple voicings.
import json, sys, itertools
OUT = sys.argv[1] if len(sys.argv) > 1 else 'holst-jupiter.json'
_id = itertools.count(1)
nid = lambda: 'hj' + format(next(_id), 'x')
STEPS = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}
def pitch(n):
    st = STEPS[n[0]]; i = 1; a = 0
    while i < len(n) and n[i] in 'b#': a += -1 if n[i] == 'b' else 1; i += 1
    return {'s': int(n[i:]) * 7 + st, 'a': a}
DUR = {'1': (1, 0), '2.': (2, 1), '2': (2, 0), '4.': (4, 1), '4': (4, 0), '8.': (8, 1), '8': (8, 0), '16': (16, 0)}
TICKS = {'1': 1920, '2.': 1440, '2': 960, '4.': 720, '4': 480, '8.': 360, '8': 240, '16': 120}
def ev(tok):
    """tok: 'C4+Eb4:4' | 'r:4' with marks after the length, separated by commas:
    ( ) slur start/end, ~ tie, . staccato, > accent, - tenuto, !mf dynamic, <  >h hairpins, |h hairpin end, 'text' """
    head, _, rest = tok.partition(':')
    parts = rest.split(',')
    d = parts[0]; marks = parts[1:]
    if d not in DUR: raise ValueError('bad token ' + repr(tok))
    t, dots = DUR[d]
    e = {'id': nid(), 't': t, 'dots': dots}
    if head == 'r': e['rest'] = True
    else: e['notes'] = [pitch(x) for x in head.split('+')]
    art = []
    for m in marks:
        if m == '(': e['slur'] = 'start'
        elif m == ')': e['slur'] = 'end'
        elif m == '~': [n.__setitem__('tie', True) for n in e['notes']]
        elif m == '.': art.append('stacc')
        elif m == '>': art.append('acc')
        elif m == '-': art.append('ten')
        elif m.startswith('!'): e['dyn'] = m[1:]
        elif m == '<': e['hp'] = '<'
        elif m == '>h': e['hp'] = '>'
        elif m == '|h': e['hp'] = 'end'
        elif m.startswith("'"): e['txt'] = m.strip("'"); e['txtStyle'] = 'tech'
        elif m.startswith('_'): e['txt'] = m[1:]; e['txtBelow'] = True
        elif m: raise ValueError(m)
    if art: e['art'] = art
    return e, TICKS[d]

NBARS = 41   # pickup + 40 bars
BAR = [960] + [1440] * 40
def rests(m):
    if m == 0: return [{'id': nid(), 't': 2, 'dots': 0, 'rest': True}]
    return [{'id': nid(), 'rest': True, 'full': True, 't': 1, 'dots': 0, 'ticks': 1440}]

def staff(bars_spec):
    """bars_spec: {bar: 'tok tok tok'} ; missing bars are whole rests"""
    bars = []
    for m in range(NBARS):
        s = bars_spec.get(m)
        if not s: bars.append(rests(m)); continue
        evs = []; tot = 0
        for tok in s.split(' '):
            e, tk = ev(tok); evs.append(e); tot += tk
        assert tot == BAR[m], (m, s, tot)
        bars.append(evs)
    return bars

def octv(spec, k):
    """move every pitch of a spec string by k octaves"""
    import re
    return re.sub(r'([A-G][b#]*)(\d)', lambda mm: mm.group(1) + str(int(mm.group(2)) + k), spec)

# ---------------- the tune (violins' octave in bars 1-24) ----------------
A1 = {
 1: "C4:4 C4:8,( Eb4:8,) D4:8.,( Bb3:16,)",
 2: "Eb4:8 F4:8 Eb4:4 D4:4",
 3: "C4:8 D4:8 C4:4 Bb3:4",
 4: "G3:2 G3:8 Bb3:8",
 5: "C4:4 C4:8,( Eb4:8,) D4:8.,( Bb3:16,)",
 6: "Eb4:8 F4:8 G4:4 G4:4",
 7: "G4:8,( F4:8 Eb4:4,) F4:4",
 8: "Eb4:2 Bb4:8,( G4:8,)",
}
B = {
 9: "F4:4 F4:4 Eb4:8 G4:8",
 10: "F4:4,( Bb3:4,) Bb4:8,( G4:8,)",
 11: "F4:4 F4:4 G4:8 Bb4:8",
 12: "C5:2 C5:8 D5:8",
 13: "Eb5:4 D5:4 C5:4",
 14: "Bb4:4 Eb5:4 G4:4",
 15: "F4:8 Eb4:8 F4:4 G4:4",
 16: "Bb4:2 G4:8 Bb4:8",
}
A2 = {
 17: "C5:4 C5:8,( Eb5:8,) D5:8.,( Bb4:16,)",
 18: "Eb5:8 F5:8 Eb5:4 D5:4",
 19: "C5:8 D5:8 C5:4 Bb4:4",
 20: "G4:2 G4:8 Bb4:8",
 21: "C5:4 C5:8,( Eb5:8,) D5:8.,( Bb4:16,)",
 22: "Eb5:8 F5:8 G5:4 G5:4",
 23: "G5:8,( F5:8 Eb5:4,) F5:4",
 24: "Eb5:2 Bb5:8,(,!f G5:8,)",
}
B2 = {m + 16: octv(s, 1) for m, s in B.items()}            # 25-32, an octave up (IX)
A3 = {
 33: "C6:4 C6:8,( Eb6:8,) D6:8.,( Bb5:16,)",
 34: "Eb6:8 F6:8 Eb6:4 D6:4",
 35: "C6:8 D6:8 C6:4 Bb5:4",
 36: "G5:2 G5:8 Bb5:8",
 37: "C6:4 C6:8,( Eb6:8,) D6:8.,( Bb5:16,)",
 38: "Eb6:8 F6:8 G6:4 G6:4",
 39: "G6:8 F6:8 Eb6:4 Eb6:4",
 40: "Eb6:2,>h Eb6:8,|h r:8",
}
TUNE = {0: "G3:4,!mf Bb3:4", **A1, **B, **A2, **B2, **A3}
TUNE[32] = TUNE[32].replace('G5:8', 'G5:8,!ff', 1)   # ff from the upbeat into the last verse

# ---------------- harmony: chords on beats (quarter positions) ----------------
# each bar: list of (beat, root chord tones low->high as names, bass)
H = {
 1: [(0, 'Ab C Eb', 'Ab'), (2, 'Bb D F', 'Bb')],
 2: [(0, 'Eb G Bb', 'G'), (2, 'G Bb D', 'G')],
 3: [(0, 'Ab C Eb', 'Ab'), (2, 'Eb G Bb', 'Bb')],
 4: [(0, 'Ab C Eb G', 'Ab'), (2, 'Eb G Bb', 'Bb')],
 5: [(0, 'Ab C Eb', 'Ab'), (2, 'Bb D F', 'Bb')],
 6: [(0, 'Eb G Bb', 'G'), (2, 'C Eb G', 'C')],
 7: [(0, 'Ab C Eb', 'Ab'), (2, 'Bb D F Ab', 'Ab')],
 8: [(0, 'Eb G Bb', 'Eb'), (2, 'Eb G Bb', 'G')],
 9: [(0, 'Bb D F', 'Bb'), (2, 'C Eb G', 'C')],
 10: [(0, 'Bb D F', 'D'), (2, 'Eb G Bb', 'G')],
 11: [(0, 'Bb D F', 'Bb'), (2, 'Eb G Bb', 'Eb')],
 12: [(0, 'Ab C Eb', 'Ab'), (1, 'C Eb G', 'G'), (2, 'F Ab C Eb', 'F')],
 13: [(0, 'C Eb G', 'C'), (1, 'G Bb D', 'Bb'), (2, 'Ab C Eb', 'Ab')],
 14: [(0, 'Eb G Bb', 'G'), (1, 'Ab C Eb', 'Ab'), (2, 'Eb G Bb', 'Bb')],
 15: [(0, 'Bb D F Ab', 'Ab'), (1, 'Bb D F', 'Bb'), (2, 'Eb G Bb', 'G')],
 16: [(0, 'Bb D F', 'Bb'), (2, 'Eb G Bb', 'Eb')],
}
for m in range(17, 25): H[m] = H[m - 16]
for m in range(25, 33): H[m] = H[m - 16]
for m in range(33, 39): H[m] = H[m - 32]
H[39] = [(0, 'Ab C Eb', 'Ab'), (2, 'Eb G Bb', 'G')]
H[40] = [(0, 'Eb G Bb', 'G')]
NOTE_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
def pc(n): return (NOTE_PC[n[0]] + n[1:].count('#') - n[1:].count('b')) % 12
def midi(n):
    p = pitch(n); s, a = p['s'], p['a']; return 12 * (s // 7 + 1) + [0, 2, 4, 5, 7, 9, 11][s % 7] + a
def at_or_above(name, lo):
    """the note called name (no octave) at or above midi lo, spelled with octave"""
    for o in range(0, 9):
        n = f'{name}{o}'
        if midi(n) >= lo: return n
def voicing(tones, lo, k=3):
    """k close-position notes of the chord from the lowest at or above lo"""
    names = tones.split(); out = []; cur = lo
    # start with the chord tone nearest above lo, then go up through the chord
    start = min(range(len(names)), key=lambda i: (midi(at_or_above(names[i], lo)) - lo))
    i = start
    while len(out) < k:
        n = at_or_above(names[i % len(names)], cur); out.append(n); cur = midi(n) + 1; i += 1
    return '+'.join(out)
def beats_pattern(m, make, rest_between=True, dyn=None, last=None):
    """the chords of bar m as quarter notes on their beats (rests between), via make(tones, bass)->pitch str"""
    hs = H.get(m)
    if not hs: return None
    out = []; pos = 0; first = True
    for i, (b, tones, bass) in enumerate(hs):
        while pos < b:
            out.append('r:4'); pos += 1
        nxt = hs[i + 1][0] if i + 1 < len(hs) else 3
        ln = nxt - b if not rest_between else 1
        d = {1: '4', 2: '2', 3: '2.'}[ln]
        tok = f'{make(tones, bass)}:{d}'
        if first and dyn: tok += f',!{dyn}'
        out.append(tok); pos += ln; first = False
    while pos < 3: out.append('r:4'); pos += 1
    return ' '.join(out)
def bass_note(oct_lo):
    return lambda tones, bass: at_or_above(bass, oct_lo)

def spec_for(bars, fn):
    return {m: fn(m) for m in bars if fn(m)}

ALL = range(1, 41)
# ---------------- the parts ----------------
P = []
def part(inst, name, abbr, clef, bars):
    P.append({'id': nid(), 'inst': inst, 'name': name, 'abbr': abbr, 'mix': None, 'staves': [{'id': nid(), 'clef': clef, 'bars': staff(bars)}]})
def part2(inst, name, abbr, clefs, bars2):
    P.append({'id': nid(), 'inst': inst, 'name': name, 'abbr': abbr, 'mix': None, 'staves': [{'id': nid(), 'clef': c, 'bars': staff(b)} for c, b in zip(clefs, bars2)]})

def tune(rng, k=0, dyn_at=None, extra=None):
    d = {m: (octv(TUNE[m], k) if k else TUNE[m]) for m in rng if m in TUNE}
    if dyn_at:
        for m, dy in dyn_at.items():
            if m in d:
                toks = d[m].split(); f = next(i for i, t in enumerate(toks) if not t.startswith('r:'))
                toks[f] = __import__('re').sub(r',!\w+', '', toks[f]) + f',!{dy}'; d[m] = ' '.join(toks)
    if extra: d.update(extra)
    return d

# Picc.: the last verse, an octave over the flutes
part('piccolo', 'Piccolo', 'Picc.', 'treble', tune(range(33, 41), 0, {33: 'ff'}))
# Flutes a2: from IX, the tune two octaves up... (flutes double the violins at IX: an octave over the violas)
part('flute', 'Flutes 1, 2', 'Fl.', 'treble', tune(range(24, 41), 0, {24: 'f'}))
part('oboe', 'Oboes 1–3', 'Ob.', 'treble', tune(range(24, 41), -1, {24: 'f'}))
part('englishhorn', 'English Horn', 'E. H.', 'treble', tune(range(24, 41), -1, {24: 'f'}))
# Clarinets: chords (A), the tune a3 from bar 13, then with the tune to the end
cl = {m: beats_pattern(m, lambda t, b: voicing(t, midi('Eb4')), dyn='mf' if m == 1 else None) for m in range(1, 13)}
cl.update(tune(range(13, 25), -1 if False else 0))
cl[13] = cl[13].replace(':4', ':4,!mf', 1)
cl.update(tune(range(25, 41), -1))
part('clarinet', 'Clarinets in B♭ 1–3', 'Cl.', 'treble', cl)
part('bassclarinet', 'Bass Clarinet in B♭', 'B. Cl.', 'treble', {m: beats_pattern(m, bass_note(midi('Ab2')), dyn={1: 'mf', 25: 'f', 33: 'ff'}.get(m)) for m in ALL})
part('bassoon', 'Bassoons 1–3', 'Bsn.', 'bass', {m: beats_pattern(m, lambda t, b: voicing(t, midi('Eb3')), dyn={1: 'mf', 25: 'f', 33: 'ff'}.get(m)) for m in ALL})
part('contrabassoon', 'Contrabassoon', 'Cbsn.', 'bass', {m: beats_pattern(m, bass_note(midi('Ab1')), dyn={1: 'mf', 25: 'f', 33: 'ff'}.get(m)) for m in ALL})
# Horns: the tune a2 on each staff in the first verse ("non legato"), chords in the middle, the tune again ff
hn = tune(range(0, 9))
hn[2] = hn[2].replace('Eb4:8', "Eb4:8,_non\u00a0legato", 1)
hnc = {m: beats_pattern(m, lambda t, b: voicing(t, midi('Bb3'), 2), rest_between=False, dyn='mp' if m == 9 else None) for m in range(9, 25)}
for nm in ('Horns 1, 2', 'Horns 3, 4', 'Horns 5, 6'):
    d = dict(hn); d.update(hnc)
    d.update(tune(range(32, 41), -1, {32: 'ff'}))
    part('horn', nm, 'Hn.', 'treble', d)
# Trumpet 1: "Solo, mf dolce" from bar 12 to 23, then the last verse ff
t1 = tune(range(12, 24)); t1[12] = t1[12].replace('C5:2', "C5:2,!mf,'1\u00a0Solo\u00a0dolce", 1)
t1.update(tune(range(32, 41), -1, {32: 'ff'}))
part('trumpet', 'Trumpet 1 in B♭', 'Tpt. 1', 'treble', t1)
part('trumpet', 'Trumpets 2, 3 in B♭', 'Tpt. 2, 3', 'treble', {m: beats_pattern(m, lambda t, b: voicing(t, midi('F4'), 2), dyn={25: 'mf', 33: 'ff'}.get(m)) for m in range(25, 41)})
part('trombone', 'Tenor Trombones', 'Ten. Tbn.', 'tenor', {m: beats_pattern(m, lambda t, b: voicing(t, midi('Bb3'), 2), dyn={33: 'ff'}.get(m)) for m in range(33, 41)})
part('basstrombone', 'Bass Trombone', 'B. Tbn.', 'bass', {m: beats_pattern(m, bass_note(midi('Bb2')), dyn={25: 'mf', 33: 'ff'}.get(m)) for m in range(25, 41)})
part('euphonium', 'Tenor Tuba', 'Ten. Tba.', 'bass', tune(range(30, 41), -2, {30: 'mf', 32: 'ff'}))
part('tuba', 'Bass Tuba', 'B. Tba.', 'bass', {m: beats_pattern(m, bass_note(midi('Eb2')), dyn={33: 'ff'}.get(m)) for m in range(33, 41)})
# Timpani (Eb, Bb, G, Ab): from IX
def timp(t, b):
    for n in ('Bb2', 'Eb2', 'G2', 'Ab2', 'C3', 'F2'):
        if pc(n[:-1]) == pc(b): return n
    return 'Bb2'
tp = {m: beats_pattern(m, timp, dyn={25: 'mf', 33: 'ff'}.get(m)) for m in range(25, 40)}
tp[40] = 'Eb2:2.,>h'
part('timpani', 'Timpani', 'Timp.', 'bass', tp)
# Harps (a2): the chords on the beats all through, the bass in the left hand
hr = {m: beats_pattern(m, lambda t, b: voicing(t, midi('Eb3') if m < 25 else midi('Bb3'), 3), dyn={1: 'mf', 25: 'f', 33: 'ff'}.get(m)) for m in ALL}
hl = {m: beats_pattern(m, lambda t, b: at_or_above(b, midi('Ab1')) + '+' + at_or_above(b, midi('Ab2'))) for m in ALL}
part2('harp', 'Harps 1, 2', 'Hp.', ['bass', 'bass'], [hr, hl])
# Strings: the tune; violins up an octave from IX (II stays below), violas and cellos with the tune
part('violin1', 'Violin I', 'Vln. I', 'treble', tune(range(0, 41)))
v2 = tune(range(0, 25)); v2.update(tune(range(25, 33), -1)); v2.update(tune(range(33, 41), -1))
part('violin2', 'Violin II', 'Vln. II', 'treble', v2)
va = tune(range(0, 25), 0); va.update(tune(range(25, 41), -1))
part('violas', 'Violas', 'Vla.', 'alto', va)
vc = tune(range(0, 25), 0); vc.update(tune(range(25, 41), -2))
part('cellos', 'Violoncellos', 'Vc.', 'tenor', vc)
db = {m: beats_pattern(m, bass_note(midi('Ab1')), dyn={1: 'mf', 25: 'f', 33: 'ff'}.get(m)) for m in ALL}
db[1] = db[1].replace(':4', ":4,'pizz.", 1); db[15] = db[15].replace(':4', ":4,'arco", 1)
part('contrabasses', 'Contrabasses', 'Cb.', 'bass', db)

measures = [{'time': [3, 4], 'key': -3, 'tempo': {'bpm': 72, 'beat': 4, 'text': 'Andante maestoso'}, 'pickup': 960}] + [{} for _ in range(40)]
measures[25]['rehearsal'] = 'IX'
measures[40]['bar'] = 'final'
score = {'v': 1, 'title': 'Jupiter', 'subtitle': 'from The Planets, Op. 32 — Andante maestoso', 'composer': 'Gustav Holst',
         'created': 0, 'layout': {'page': 'B4', 'landscape': False, 'staffMm': 3.7, 'concert': True, 'hideEmpty': True},
         'sound': {'room': 'hall', 'roomMix': 1, 'tuning': 440}, 'measures': measures, 'parts': P}
json.dump(score, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
print('parts', len(P), 'bars', len(measures))
