# Test scores engraved by LilyPond (the program Mutopia and many editions use), with their MIDI as
# the truth: random but musical lines in every clef and key, with accidentals of all kinds.
import random, subprocess, sys, os
LY = '/home/claude/dl_ly/lilypond-2.24.4/bin/lilypond'
OUT = os.environ.get('LYOUT', '/home/claude/lyb')
NAMES = ['c', 'd', 'e', 'f', 'g', 'a', 'b']
KEYS = {-4: 'aes \\major', -3: 'ees \\major', -2: 'bes \\major', -1: 'f \\major', 0: 'c \\major', 1: 'g \\major', 2: 'd \\major', 3: 'a \\major', 4: 'e \\major', -5: 'des \\major', 5: 'b \\major'}
CLEF_MID = {'treble': 35, 'bass': 23, 'alto': 29, 'tenor': 27, 'soprano': 32, 'mezzosoprano': 30}   # diatonic step of the middle line (C0 = 0)
def key_alter(key, step):
    sharps = [3, 0, 4, 1, 5, 2, 6]; flats = [6, 2, 5, 1, 4, 0, 3]   # F C G D A E B / B E A D G C F
    d = step % 7
    if key > 0 and d in sharps[:key]: return 1
    if key < 0 and d in flats[:-key]: return -1
    return 0
def note_name(step, alt, octave_mode='abs'):
    n = NAMES[step % 7] + {-2: 'eses', -1: 'es', 0: '', 1: 'is', 2: 'isis'}[alt]
    if n.startswith('ees'): pass
    n = n.replace('ees', 'es').replace('aes', 'as') if False else n
    octv = step // 7 - 3    # c (no marks) is C3 in LilyPond absolute
    return n + ("'" * octv if octv > 0 else ',' * (-octv))
def piece(seed):
    R = random.Random(seed)
    clef = R.choice(['treble', 'treble', 'bass', 'bass', 'alto', 'tenor'])
    if os.environ.get('CLEF'): clef = os.environ['CLEF']
    key = R.choice([-4, -3, -2, -1, 0, 1, 2, 3, 4])
    time = R.choice([(4, 4), (3, 4), (2, 4), (6, 8)])
    mid = CLEF_MID[clef]
    bars = []; s = mid
    beat16 = {(4, 4): 16, (3, 4): 12, (2, 4): 8, (6, 8): 12}[time]
    for m in range(14):
        left = beat16; ev = []; accs = {}
        while left > 0:
            opts = [d for d in ([1, 2, 4, 6, 8] if time != (6, 8) else [2, 4, 6]) if d <= left and (left - d) % 1 == 0]
            d = R.choice(opts if R.random() < 0.85 else [o for o in opts if o <= 4] or opts)
            if R.random() < 0.08:
                ev.append('r' + {1: '16', 2: '8', 3: '8.', 4: '4', 6: '4.', 8: '2', 12: '2.', 16: '1'}[d]); left -= d; continue
            s = max(mid - 9, min(mid + 9, s + R.choice([-2, -1, -1, 1, 1, 2, 3, -3, 0, 4, -4])))
            base = key_alter(key, s)
            alt = base
            r = R.random()
            if r < 0.12: alt = base + (1 if base < 1 else -1)          # a chromatic note
            elif r < 0.17: alt = base - 1 if base > -1 else base + 1
            alt = max(-1, min(1, alt))
            dur = {1: '16', 2: '8', 3: '8.', 4: '4', 6: '4.', 8: '2', 12: '2.', 16: '1'}[d]
            nn = note_name(s, alt)
            # a cautionary sign now and then (the sign repeats what holds anyway)
            caut = '!' if R.random() < 0.05 else ''
            if R.random() < 0.06 and d >= 2:   # a double stop
                s2 = s - R.choice([2, 4, 5]); nn2 = note_name(s2, key_alter(key, s2))
                ev.append('<' + nn2 + ' ' + nn + caut + '>' + dur)
            else: ev.append(nn + caut + dur)
            left -= d
        bars.append(' '.join(ev))
    body = ' |\n'.join(bars)
    ly = f"""\\version "2.24.0"
\\header {{ tagline = ##f }}
\\paper {{ #(set-paper-size "a4") }}
\\score {{ {{ \\clef {clef} \\key {KEYS[key]} \\time {time[0]}/{time[1]} \\accidentalStyle default
{body} \\bar "|." }}
  \\layout {{ }} \\midi {{ }} }}
"""
    return ly
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for seed in [int(x) for x in sys.argv[1].split(',')]:
        open(f'{OUT}/t{seed}.ly', 'w').write(piece(seed))
        r = subprocess.run([LY, '-s', '-o', f'{OUT}/t{seed}', f'{OUT}/t{seed}.ly'], capture_output=True, text=True)
        if r.returncode: print(seed, r.stderr[-500:])
    print(sorted(os.listdir(OUT))[:12])
