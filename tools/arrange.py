# Holst, Jupiter (the big tune, Andante maestoso) set for a classical orchestra, for Stand's
# Compose example. Melody and the hymn's chords taken from a MIDI of the tune; the orchestration
# (who plays what, octaves, the inner voices) is Stand's own.
import mido, json
m = mido.MidiFile('thaxted.mid'); T = 384; Q = 480
tr = []
for t in m.tracks:
    now = 0; on = {}; notes = []
    for msg in t:
        now += msg.time
        if msg.type == 'note_on' and msg.velocity > 0: on[msg.note] = now
        elif msg.type in ('note_off', 'note_on') and msg.note in on: s = on.pop(msg.note); notes.append((s, now - s, msg.note))
    tr.append(sorted(notes))
mel = tr[1]; BAR = 3 * T
NB = 25  # 0 = pickup (1 beat), 1..24
def melody_bar(b):
    # [(start_ticks_in_bar, dur, midi)] in Stand ticks (quarter 480); bar 0: only beat 3 -> pickup at 0
    out = []
    for s, d, n in mel:
        if s // BAR != b: continue
        pos = (s % BAR) * Q // T; dur = d * Q // T
        if b == 0: pos -= 2 * Q
        out.append([pos, dur, n])
    return out
def chord_at(b, beat):
    t0 = b * BAR + beat * T
    return sorted(n for tk in tr[2:] for s, d, n in tk if s <= t0 + 5 and s + d > t0 + 5)
def mel_at(b, beat):
    t0 = b * BAR + beat * T
    for s, d, n in mel:
        if s <= t0 + 5 and s + d > t0 + 5: return n
    return None
beats = {}  # (bar, beat) -> dict
for b in range(NB):
    for beat in range(3):
        if b == 0 and beat < 2: continue
        C = chord_at(b, beat)
        if not C:
            beats[(b, beat)] = None; continue
        bass = C[0]; up = sorted(set(C[1:]), reverse=True)
        mt = mel_at(b, beat) or 80
        under = [x for x in up if x < mt]
        v2 = under[0] if under else (up[-1] if up else bass + 12)
        rest = [x for x in under[1:]] if under else []
        # (no second inner note in the chord: the nearest note of the chord below the second violins)
        pcs = {x % 12 for x in C}
        va = rest[0] if rest else next((x for x in range(v2 - 1, v2 - 13, -1) if x % 12 in pcs), bass + 12)
        while v2 < 58: v2 += 12
        while va < 50: va += 12
        if va >= v2: va -= 12 if va - 12 >= 48 else 0
        cb = bass
        while cb > 52: cb -= 12   # cello bass at most E3
        while cb < 36: cb += 12
        beats[(b, beat)] = dict(v2=v2, va=va, vc=cb, cbass=cb - 12 if cb - 12 >= 28 else cb)
# the last bar: the full chord held
beats[(24, 1)] = beats[(24, 0)]; beats[(24, 2)] = beats[(24, 0)]
def harmony_bar(b, key, shift=0):
    beats_in = [2] if b == 0 else [0, 1, 2]
    out = []
    for beat in beats_in:
        h = beats[(b, beat)]
        n = None if h is None else h[key] + shift
        pos = 0 if b == 0 else beat * Q
        if out and out[-1][2] == n and n is not None: out[-1][1] += Q
        else: out.append([pos, Q, n])
    return [x for x in out]
def bar_len(b): return Q if b == 0 else 3 * Q
def rest_bar(b): return [[0, bar_len(b), None]]
def fill(evs, b):
    # rests where nothing plays
    out = []; pos = 0
    for p, d, n in sorted(evs, key=lambda x: x[0]):
        if p > pos: out.append([pos, p - pos, None])
        out.append([p, d, n]); pos = p + d
    if pos < bar_len(b): out.append([pos, bar_len(b) - pos, None])
    return out
A = range(0, 9); B_ = range(9, 17); C_ = range(17, 25)
def mel_part(b, shift=0, pickup_only=False):
    ev = melody_bar(b)
    if b == 24: ev = [[0, 3 * Q, ev[0][2]]]
    if pickup_only: ev = [e for e in ev if e[0] >= 2 * Q]
    return fill([[p, d, n + shift] for p, d, n in ev], b)
parts = {k: [] for k in ['flute', 'oboe', 'clarinet', 'bassoon', 'horn', 'trumpet', 'timpani', 'violin1', 'violin2', 'violas', 'cellos', 'contrabasses']}
dyn = {}
for b in range(NB):
    inA, inB, inC = b in A, b in B_, b in C_
    parts['violin1'].append(mel_part(b))
    parts['violin2'].append(harmony_bar(b, 'v2'))
    parts['violas'].append(harmony_bar(b, 'va'))
    parts['cellos'].append(harmony_bar(b, 'vc'))
    parts['contrabasses'].append(harmony_bar(b, 'cbass'))
    parts['horn'].append(mel_part(b, -12) if (inA or inC or b == 16) and not (b == 16) else (harmony_bar(b, 'va') if inB else rest_bar(b)))
    if b == 16: parts['horn'][-1] = mel_part(b, -12, pickup_only=True)
    parts['oboe'].append(mel_part(b) if (inB or inC) else rest_bar(b))
    parts['flute'].append(mel_part(b, 12) if inC else (mel_part(b, 12, pickup_only=True) if b == 16 else rest_bar(b)))
    parts['trumpet'].append(mel_part(b) if inC else (mel_part(b, 0, pickup_only=True) if b == 16 else rest_bar(b)))
    parts['clarinet'].append(harmony_bar(b, 'v2') if (inB or inC) else rest_bar(b))
    parts['bassoon'].append(harmony_bar(b, 'vc') if (inB or inC) else rest_bar(b))
    # timpani: E flat and B flat, on the first beat of the bars of the last phrase whose bass is one of them
    if inC:
        h = beats[(b, 0)]; pc = h['vc'] % 12 if h else None
        parts['timpani'].append(fill([[0, Q if b < 24 else 3 * Q, 51 if pc == 3 else 46]], b) if pc in (3, 10) else rest_bar(b))
    else: parts['timpani'].append(rest_bar(b))
json.dump({'parts': parts}, open('arr.json', 'w'))
for k, v in parts.items(): print(k, v[1], v[17])
