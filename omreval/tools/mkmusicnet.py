# musicnet: real chamber-music recordings (MusicNet, Zenodo 5120004) with every note aligned to the
# score. For each recording: one player's part engraved from the score MIDI (the soloist with piano;
# the first violin of a quartet; the top part of a wind group; the instrument itself when solo), its
# first page; the recording's first 100 s. Every bar's start = the time of its first beat, from the
# aligned notes of all the players (beat -> time, interpolated between the beats heard).
# (the audio: mkmusicnet_stream.py, run in /home/claude/musicnet, keeps the chosen recordings' first 100 s)
# Out: musicnet/<id>.pdf, musicnet.json { id: { page, wav, T (None = a bar that starts before any note,
# not scored), ens } }
import os, sys, csv, json, re, subprocess, glob
import numpy as np
from music21 import converter, stream, instrument, meter
M = '/home/claude/musicnet'; OUT = '/home/claude/omreval/musicnet'; LY = '/home/claude/dl_ly/lilypond-2.24.4/bin/'
os.makedirs(OUT, exist_ok=True)
meta_csv = {r['id']: r for r in csv.DictReader(open(f'{M}/musicnet_metadata.csv'))}
meta = json.load(open(f'{OUT}/musicnet.json')) if os.path.exists(f'{OUT}/musicnet.json') else {}
def is_keys(p):
    i = p.getInstrument(returnDefault=True)
    nm = (i.instrumentName or '') + ' ' + (p.partName or '')
    return isinstance(i, (instrument.Piano, instrument.Harpsichord, instrument.KeyboardInstrument)) or re.search(r'piano|harpsi|klavier', nm, re.I)
def engrave(part, nm, nbars):
    sc = stream.Score(); pp = stream.Part()
    ms = list(part.getElementsByClass('Measure'))[:nbars]
    for m in ms: pp.append(m)
    sc.insert(0, pp)
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
    os.remove(ly)
    pdf = f'{OUT}/{nm}.pdf'
    if not os.path.exists(pdf): return None
    pages = int(next((l.split()[-1] for l in subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout.splitlines() if l.startswith('Pages')), '1'))
    if pages > 1:
        os.remove(pdf)
        return engrave(part, nm, nbars - 3) if nbars > 9 else None
    return nbars
for wav in sorted(glob.glob(f'{M}/audio/*.wav')):
    rid = os.path.basename(wav)[:-4]
    if rid in meta: continue
    try:
        ens = meta_csv[rid]['ensemble']
        mid = glob.glob(f'{M}/musicnet_midis/*/{rid}_*.mid')
        if not mid: print(rid, 'no midi'); continue
        s = converter.parse(mid[0], quantizePost=True)
        parts = list(s.parts)
        nonkeys = [p for p in parts if not is_keys(p)]
        part = parts[0] if ens == 'Solo Piano' else (nonkeys or parts)[0]
        # (the beats heard: each aligned note's score beat and its time)
        L = list(csv.DictReader(open(f'{M}/labels/{rid}.csv')))
        # (a repeat played: the beats go back. Only the playing up to there is used)
        L.sort(key=lambda x: int(x['start_time'])); hi = -1; cut = None
        for x in L:
            b = float(x['start_beat'])
            if b < hi - 2: cut = int(x['start_time']) / 44100; break
            hi = max(hi, b)
        if cut is not None: L = [x for x in L if int(x['start_time']) / 44100 < cut]
        bt = {}
        for x in L: bt.setdefault(round(float(x['start_beat']), 3), []).append(int(x['start_time']) / 44100)
        bb = np.array(sorted(bt)); tt = np.array([np.median(bt[b]) for b in bb])
        # (a beat heard out of order — a misaligned note — is dropped)
        keep = [0]
        for i in range(1, len(bb)):
            if tt[i] > tt[keep[-1]]: keep.append(i)
        bb, tt = bb[keep], tt[keep]
        ms = list(part.getElementsByClass('Measure'))
        # (MusicNet counts beats in the time signature's own unit — eighths in 3/8 — so each bar's start
        # in those beats: the bars before it, each its length in its own beats)
        starts = []; acc = 0.0; den = 4
        for m in ms:
            tsm = m.timeSignature or (m.getContextByClass(meter.TimeSignature))
            if tsm is not None: den = tsm.denominator
            starts.append(acc); acc += float(m.duration.quarterLength) * den / 4
        T = []
        for b in starts:
            if b < bb[0] - 1e-6 or b > bb[-1]: T.append(None if b < bb[0] else np.nan); continue
            T.append(float(np.interp(b, bb, tt)))
        # (the bars inside the 100 s)
        n = 0
        while n + 1 < len(T) and (T[n + 1] is None or (not np.isnan(T[n + 1]) and T[n + 1] < min(97, (cut or 999) - 0.5))): n += 1
        if n < 6: print(rid, 'too few bars', n); continue
        nb = engrave(part, rid, min(n, 40))
        if not nb: print(rid, 'no page'); continue
        Tn = T[:nb + 1]
        if any(t is not None and np.isnan(t) for t in Tn): print(rid, 'gap'); continue
        if Tn[0] is not None: Tn[0] = max(0.0, Tn[0])
        meta[rid] = {'page': f'{rid}.pdf', 'wav': wav, 'T': [None if t is None else round(t, 4) for t in Tn], 'ens': ens, 'part': part.partName}
        json.dump(meta, open(f'{OUT}/musicnet.json', 'w'), indent=0)
        print(rid, ens, part.partName, 'bars', nb, flush=True)
    except Exception as e:
        import traceback; traceback.print_exc(); print('fail', rid, e)
