# Streams MusicNet's 11 GB archive once and keeps only the chosen recordings: the first SECS seconds,
# mono 22 050 Hz, plus their note labels. Nothing else touches the disk.
import tarfile, urllib.request, csv, io, wave, os, sys
import numpy as np
SECS = 100; SR = 22050
URL = 'https://zenodo.org/records/5120004/files/musicnet.tar.gz?download=1'
WANT = {'Solo Cello': 12, 'Accompanied Cello': 7, 'Clarinet-Cello-Piano Trio': 3, 'Accompanied Violin': 14, 'Solo Violin': 6,
        'Accompanied Clarinet': 4, 'Solo Flute': 3, 'String Quartet': 14, 'Wind Quintet': 5, 'Piano Trio': 7,
        'Violin and Harpsichord': 4, 'Horn Piano Trio': 4, 'Piano Quartet': 4, 'Clarinet Quintet': 3, 'Solo Piano': 10}
meta = list(csv.DictReader(open('musicnet_metadata.csv')))
pick = set(); cnt = {}
for r in meta:
    e = r['ensemble']
    if cnt.get(e, 0) < WANT.get(e, 0): pick.add(r['id']); cnt[e] = cnt.get(e, 0) + 1
print('picked', len(pick), flush=True)
os.makedirs('audio', exist_ok=True); os.makedirs('labels', exist_ok=True)
got = 0
with urllib.request.urlopen(URL, timeout=120) as f:
    tf = tarfile.open(fileobj=f, mode='r|gz')
    for m in tf:
        base = os.path.basename(m.name); stem = os.path.splitext(base)[0]
        if stem not in pick or not m.isfile(): continue
        data = tf.extractfile(m).read()
        if base.endswith('.csv'):
            open(f'labels/{base}', 'wb').write(data)
        elif base.endswith('.wav'):
            w = wave.open(io.BytesIO(data)); sr = w.getframerate(); ch = w.getnchannels(); sw = w.getsampwidth()
            n = min(w.getnframes(), SECS * sr)
            x = np.frombuffer(w.readframes(n), np.int16 if sw == 2 else np.int32).astype(np.float32)
            if sw == 4: x /= 65536
            if ch == 2: x = x.reshape(-1, 2).mean(1)
            k = int(len(x) * SR / sr); y = np.interp(np.arange(k) * sr / SR, np.arange(len(x)), x)
            o = wave.open(f'audio/{stem}.wav', 'wb'); o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR); o.writeframes(np.clip(y, -32768, 32767).astype(np.int16).tobytes()); o.close()
            got += 1; print('kept', stem, m.name, flush=True)
print('done', got)
