# fixasap2: a score that opens with a pickup bar (measure shorter than its time signature) whose beats
# ASAP does not annotate: mkasap took page bar 0 (the pickup) to start at the first downbeat, so every bar
# was one bar early in the truth. Now the pickup bar's start is unknown (None, not scored) and bar i
# starts at the i-th downbeat.
import json, csv
from music21 import converter
OUT = '/home/claude/omreval/asap'
meta = json.load(open(f'{OUT}/asap.json'))
rows = {r['midi_performance']: r for r in csv.DictReader(open('/home/claude/asap/metadata.csv'))}
for k, m in meta.items():
    if 'pk' in m: continue
    m['pk'] = False
    if m['pickup']: continue
    s = converter.parse('/home/claude/asap/' + rows[m['perf']]['xml_score'])
    m0 = s.parts[0].getElementsByClass('Measure')[0]
    if m0.duration.quarterLength < m0.barDuration.quarterLength - 1e-6:
        nb = len(m['T']) - 1
        m['T'] = [None] + m['T'][:nb]; m['pk'] = True
        print(k, 'pickup bar not annotated: shifted', flush=True)
json.dump(meta, open(f'{OUT}/asap.json', 'w'), indent=0)
