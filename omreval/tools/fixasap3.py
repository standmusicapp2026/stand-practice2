# fixasap3: fixasap2 took a first measure shorter than its time signature in ASAP's score for a pickup
# ASAP does not annotate, and shifted the truth a bar. Where the performance's first note IS the first
# annotated downbeat, nothing was played before it: no unannotated pickup, so the shift is undone
# (bar i at the i-th downbeat again, as mkasap had it).
import json
import pretty_midi
OUT = '/home/claude/omreval/asap'; A = '/home/claude/asap'
meta = json.load(open(f'{OUT}/asap.json')); ann = json.load(open(f'{A}/asap_annotations.json'))
for k, m in meta.items():
    if not m.get('pk') or m.get('pk3'): continue
    an = ann[m['perf']]; pm = pretty_midi.PrettyMIDI(f'{A}/{m["perf"]}')
    fa = min(n.start for i in pm.instruments for n in i.notes); dbs = an['performance_downbeats']; beats = an['performance_beats']
    if fa < dbs[0] - 0.1: continue
    nb = len(m['T']) - 1
    a0 = max(0.0, dbs[0] - 1.5)
    end = dbs[nb] if nb < len(dbs) else beats[-1] + (beats[-1] - beats[-2])
    T = [round(t - a0 - m.get('lead', 0), 4) for t in dbs[:nb]] + [round(end - a0 - m.get('lead', 0), 4)]
    # (the same as before the shift, where both have it)
    assert all(abs(a - b) < 0.01 for a, b in zip(T[:-1], m['T'][1:])), (k, T[:4], m['T'][:4])
    m['T'] = T; m['pk'] = False; m['pk3'] = True
    print(k, 'no pickup played: shift undone', flush=True)
json.dump(meta, open(f'{OUT}/asap.json', 'w'), indent=0)
# And the other way: a first bar that is nearly all rests (its first note in its last tenth: a flourish
# into bar 1), whose first note IS the first annotated downbeat: ASAP put bar 1's downbeat on that
# flourish, so the truth was a bar early. Shifted as fixasap2 does (bar 0's start unknown).
import csv
from music21 import converter
rows = {r['midi_performance']: r for r in csv.DictReader(open(f'{A}/metadata.csv'))}
for k, m in meta.items():
    if m.get('pk') or m.get('pickup') or m.get('pk3') or m.get('pk4'): continue
    s = converter.parse(f'{A}/' + rows[m['perf']]['xml_score'])
    fs = []
    for p in s.parts:
        m0 = p.getElementsByClass('Measure')[0]; ns = [n.offset for n in m0.recurse().notes]
        if ns: fs.append(min(ns))
    q = min(fs) / m0.barDuration.quarterLength if fs else 0
    if q < 0.9: continue
    an = ann[m['perf']]; pm = pretty_midi.PrettyMIDI(f'{A}/{m["perf"]}')
    fa = min(n.start for i in pm.instruments for n in i.notes)
    if abs(fa - an['performance_downbeats'][0]) > 0.15: continue
    nb = len(m['T']) - 1
    m['T'] = [None] + m['T'][:nb]; m['pk4'] = True
    print(k, 'flourish taken for bar 1: shifted', flush=True)
json.dump(meta, open(f'{OUT}/asap.json', 'w'), indent=0)
