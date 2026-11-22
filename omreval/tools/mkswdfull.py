# swdfull: Winterreise, whole songs. The singer's part engraved whole (as many pages as it takes), the
# whole recording (HU33, SC06), every bar's start from the hand annotations. Songs whose performance
# repeats bars (annotations going back) are left out for now (the page has no repeat marks to follow).
# Out: swdfull/<song>.pdf, swdfull.json { "<song>-<who>": { page, wav, T } }
import os, sys, csv, json, re, subprocess
from music21 import converter, stream
D = '/home/claude/swd'; OUT = '/home/claude/omreval/swdfull'; LY = '/home/claude/dl_ly/lilypond-2.24.4/bin/'
os.makedirs(OUT, exist_ok=True)
def meas(song, who):
    rows = list(csv.reader(open(f'{D}/02_Annotations/ann_audio_measure/Schubert_D911-{song:02d}_{who}.csv'), delimiter=';'))[1:]
    seq = [(float(t), int(float(m))) for t, m in rows]
    return seq
def engrave(song, nm):
    s = converter.parse(f'{D}/01_RawData/score_musicxml/Schubert_D911-{song:02d}.xml')
    v = s.parts[0]
    for n in v.recurse().notes: n.lyrics = []
    sc = stream.Score(); sc.insert(0, v)
    xml = f'{OUT}/{nm}.musicxml'; sc.write('musicxml', fp=xml)
    tx = open(xml).read(); tx = re.sub(r'<defaults>.*?</defaults>', '', tx, flags=re.S); tx = re.sub(r'<print[^>]*/>', '', tx); tx = re.sub(r'<print[^>]*>.*?</print>', '', tx, flags=re.S)
    tx = re.sub(r'<credit[^>]*>.*?</credit>', '', tx, flags=re.S)
    # (tempo marks and words above the staff left out: LilyPond runs them into the numbers of bars of rest)
    tx = re.sub(r'<direction[^>]*>(?:(?!</direction>).)*?<(?:words|metronome)\b.*?</direction>', '', tx, flags=re.S); open(xml, 'w').write(tx)
    ly = f'{OUT}/{nm}.ly'
    subprocess.run([LY + 'musicxml2ly', '--no-beaming', '-o', ly, xml], capture_output=True, timeout=120)
    t = open(ly).read().replace('\\header {', '\\header { tagline = ##f ', 1).replace('\\pageBreak', '').replace('\\break', '')
    t = re.sub(r'title = +"[^"]*"', f'title = "{nm}"', t); t = re.sub(r'composer = +"[^"]*"', 'composer = ""', t)
    t = t.replace('\\version', '#(set-default-paper-size "a4")\n#(set-global-staff-size 20)\n\\version', 1)
    open(ly, 'w').write(t)
    subprocess.run([LY + 'lilypond', '-s', '-o', f'{OUT}/{nm}', ly], capture_output=True, timeout=240)
    os.path.exists(ly) and os.remove(ly)
    return [m.number for m in v.getElementsByClass('Measure')] if os.path.exists(f'{OUT}/{nm}.pdf') else None
meta = {}
for song in range(1, 25):
    nm = f's{song:02d}'
    try:
        bars = engrave(song, nm)
        if not bars: print(nm, 'no pdf'); continue
        for who in ['HU33', 'SC06']:
            seq = meas(song, who)
            ms = [m for _, m in seq[:-1]]
            if any(b <= a for a, b in zip(ms, ms[1:])): print(nm, who, 'repeats: left out'); continue
            M = {m: t for t, m in seq[:-1]}
            if any(b not in M for b in bars): print(nm, who, 'bars not all annotated', [b for b in bars if b not in M][:5]); continue
            T = [M[b] for b in bars] + [seq[-1][0]]
            meta[f'{nm}-{who}'] = {'page': f'{nm}.pdf', 'wav': f'{D}/01_RawData/audio_wav/Schubert_D911-{song:02d}_{who}.wav', 'T': [round(t, 4) for t in T]}
            print(nm, who, 'bars', len(bars), flush=True)
    except Exception as e:
        print('fail', nm, e)
json.dump(meta, open(f'{OUT}/swdfull.json', 'w'), indent=0)
print('total', len(meta), 'runs', sum(len(m['T']) - 1 for m in meta.values()), 'bars')
