# fixasap: ASAP's performance MIDI for a piece cut out of a longer MAESTRO recording does not start at
# the recording's `start` — its first note is put at 0.5 s (or another lead). mkasap took ASAP times as
# recording time - start, so those pieces' bar times were late by that lead. Here the lead is measured
# (ASAP's first note against MAESTRO's first note after `start`) and taken off each bar's time, once.
import csv, json, io
import pretty_midi
from remotezip import RemoteZip
OUT = '/home/claude/omreval/asap'
ZIP = 'https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip'
z = RemoteZip(ZIP)
rows = {r['midi_performance']: r for r in csv.DictReader(open('/home/claude/asap/metadata.csv'))}
meta = json.load(open(f'{OUT}/asap.json'))
for k, m in meta.items():
    if 'lead' in m: continue
    r = rows[m['perf']]
    if not r['start']: m['lead'] = 0.0; continue
    st = float(r['start'])
    a = pretty_midi.PrettyMIDI('/home/claude/asap/' + r['midi_performance'])
    mm = pretty_midi.PrettyMIDI(io.BytesIO(z.read('maestro-v3.0.0/' + r['maestro_midi_performance'].replace('{maestro}/', ''))))
    fa = min(n.start for i in a.instruments for n in i.notes)
    fm = min(n.start for i in mm.instruments for n in i.notes if n.start >= st - 0.05) - st
    d = round(fa - fm, 4)
    m['lead'] = d
    if abs(d) > 0.002: m['T'] = [round(t - d, 4) for t in m['T']]
    print(k, 'lead', d, flush=True)
json.dump(meta, open(f'{OUT}/asap.json', 'w'), indent=0)
