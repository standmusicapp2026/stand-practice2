# asap: real piano performances (ASAP dataset, its audio from MAESTRO v3), every beat and bar annotated.
# For each piece (one performance): the score's first page engraved (LilyPond, both staves), the
# recording from just before its first note to just after the last bar of that page, mono 22 050 Hz.
# The MAESTRO zip is read in place (only the needed file is fetched).
# AFTER IT: run fixasap.py (ASAP's cut-out MIDI puts its first note 0.5 s in, so those bar times are
# corrected) and fixasap2.py (a pickup bar ASAP does not annotate: bars were one early in the truth).
# Out: asap/<key>.wav, <key>.pdf, asap.json { key: { bars: [xml measure numbers], T: [start of each bar..., end] } }
import os, sys, csv, json, wave, re, subprocess, io, ast, random
import numpy as np
from music21 import converter, stream
A = '/home/claude/asap'; OUT = '/home/claude/omreval/asap'; LY = '/home/claude/dl_ly/lilypond-2.24.4/bin/'
ZIP = 'https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip'
os.makedirs(OUT, exist_ok=True)
SR = 22050
ann = json.load(open(f'{A}/asap_annotations.json'))
rows = [r for r in csv.DictReader(open(f'{A}/metadata.csv')) if r['maestro_audio_performance']]
# one performance per piece, pieces in a fixed random order
seen = {}; random.seed(11)
for r in rows: seen.setdefault(r['folder'], []).append(r)
pieces = sorted(seen); random.shuffle(pieces)
LIMIT = int(os.environ.get('LIMIT', 40)); SKIP = int(os.environ.get('SKIP', 0))
meta = json.load(open(f'{OUT}/asap.json')) if os.path.exists(f'{OUT}/asap.json') else {}
_z = None
def zipf():
    global _z
    if _z is None:
        from remotezip import RemoteZip
        _z = RemoteZip(ZIP)
    return _z
def engrave(xmlpath, nm, nbars):
    s = converter.parse(xmlpath)
    parts = list(s.parts)
    ms0 = list(parts[0].getElementsByClass('Measure'))
    if len(ms0) < 6: return None
    nbars = min(nbars, len(ms0))
    sc = stream.Score()
    for p in parts:
        ms = list(p.getElementsByClass('Measure'))[:nbars]
        np_ = stream.Part(); np_.id = p.id
        for e in p.getElementsByClass(['Instrument']): np_.insert(0, e)
        for m in ms: np_.append(m)
        sc.insert(0, np_)
    xml = f'{OUT}/{nm}.musicxml'; sc.write('musicxml', fp=xml)
    tx = open(xml).read(); tx = re.sub(r'<defaults>.*?</defaults>', '', tx, flags=re.S); tx = re.sub(r'<print[^>]*/>', '', tx); tx = re.sub(r'<print[^>]*>.*?</print>', '', tx, flags=re.S)
    tx = re.sub(r'<credit[^>]*>.*?</credit>', '', tx, flags=re.S)
    # (tempo marks and words above the staff left out: LilyPond runs them into the numbers of bars of rest)
    tx = re.sub(r'<direction[^>]*>(?:(?!</direction>).)*?<(?:words|metronome)\b.*?</direction>', '', tx, flags=re.S); open(xml, 'w').write(tx)
    ly = f'{OUT}/{nm}.ly'
    subprocess.run([LY + 'musicxml2ly', '--no-beaming', '-o', ly, xml], capture_output=True, timeout=120)
    if not os.path.exists(ly): return None
    t = open(ly).read().replace('\\header {', '\\header { tagline = ##f ', 1).replace('\\pageBreak', '').replace('\\break', '')
    t = re.sub(r'title = +"[^"]*"', f'title = "{nm}"', t); t = re.sub(r'composer = +"[^"]*"', 'composer = ""', t)
    t = t.replace('\\version', '#(set-default-paper-size "a4")\n#(set-global-staff-size 20)\n\\version', 1)
    open(ly, 'w').write(t)
    subprocess.run([LY + 'lilypond', '-s', '-o', f'{OUT}/{nm}', ly], capture_output=True, timeout=240)
    pdf = f'{OUT}/{nm}.pdf'
    if not os.path.exists(pdf): return None
    pages = int(next((l.split()[-1] for l in subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout.splitlines() if l.startswith('Pages')), '1'))
    if pages > 1:
        os.remove(pdf)
        return engrave(xmlpath, nm, nbars - 3) if nbars > 9 else None
    for ext in ('.ly',): os.path.exists(f'{OUT}/{nm}{ext}') and os.remove(f'{OUT}/{nm}{ext}')
    return nbars
def audio(r, a, b, nm):
    name = 'maestro-v3.0.0/' + r['maestro_audio_performance'].replace('{maestro}/', '')
    raw = zipf().read(name)
    w = wave.open(io.BytesIO(raw)); sr = w.getframerate(); ch = w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    if ch == 2: x = x.reshape(-1, 2).mean(1)
    x = x[int(max(0, a) * sr): int(b * sr)]
    # (to 22 050 Hz)
    n = int(len(x) * SR / sr); y = np.interp(np.arange(n) * sr / SR, np.arange(len(x)), x)
    o = wave.open(f'{OUT}/{nm}.wav', 'wb'); o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR); o.writeframes(np.clip(y, -32768, 32767).astype(np.int16).tobytes()); o.close()
done = 0
for folder in pieces[SKIP:]:
    if done >= LIMIT: break
    r = seen[folder][0]
    key = re.sub(r'[^A-Za-z0-9]+', '_', folder).strip('_')
    if key in meta: continue
    try:
        an = ann[r['midi_performance']]
        if str(an.get('score_and_performance_aligned')) != 'True': print(key, 'not aligned'); continue
        beats = an['performance_beats']; dbs = an['performance_downbeats']; smap = an['downbeats_score_map']
        if isinstance(smap, str): smap = ast.literal_eval(smap)
        # the bars, in order and without repeats, as far as the performance goes straight on
        k = 1
        while k < len(smap) and smap[k] == smap[k - 1] + 1: k += 1
        pickup = beats[0] < dbs[0] - 0.05
        nb = engrave(f'{A}/{r["xml_score"]}', key, min(k + (1 if pickup else 0), 32))
        if not nb: print(key, 'no page'); continue
        nfull = nb - (1 if pickup else 0)
        if nfull + 1 > len(dbs): print(key, 'short'); continue
        T = ([beats[0]] if pickup else []) + dbs[:nfull]
        end = dbs[nfull] if nfull < len(dbs) else beats[-1] + (beats[-1] - beats[-2])
        st = float(r['start'] or 0)
        a0 = max(0.0, T[0] - 1.5)
        audio(r, st + a0, st + end + 3.0, key)
        meta[key] = {'bars': nb, 'pickup': pickup, 'T': [round(t - a0, 4) for t in T] + [round(end - a0, 4)], 'perf': r['midi_performance']}
        json.dump(meta, open(f'{OUT}/asap.json', 'w'), indent=0)
        done += 1
        print(key, 'bars', nb, 'pickup', pickup, 'secs', round(end - a0 + 3, 1), flush=True)
    except Exception as e:
        import traceback; traceback.print_exc(); print('fail', key, e)
