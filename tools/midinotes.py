# The notes of a MIDI file, in order (onset, pitch), all tracks together: the truth for a score page
import sys, json, struct
def read(path):
    d = open(path, 'rb').read(); i = 0
    def u32(): nonlocal i; v = struct.unpack('>I', d[i:i+4])[0]; i += 4; return v
    def u16(): nonlocal i; v = struct.unpack('>H', d[i:i+2])[0]; i += 2; return v
    assert d[:4] == b'MThd'; i = 4; ln = u32(); fmt, ntr, div = u16(), u16(), u16(); i = 8 + ln
    notes = []
    for _ in range(ntr):
        if d[i:i+4] != b'MTrk': break
        i += 4; ln = u32(); end = i + ln; t = 0; run = 0
        while i < end:
            v = 0
            while True:
                b = d[i]; i += 1; v = (v << 7) | (b & 127)
                if b < 128: break
            t += v; st = d[i]
            if st == 0xFF: i += 2; l = 0
            if st == 0xFF:
                l = 0
                while True:
                    b = d[i]; i += 1; l = (l << 7) | (b & 127)
                    if b < 128: break
                i += l; continue
            if st in (0xF0, 0xF7):
                i += 1; l = 0
                while True:
                    b = d[i]; i += 1; l = (l << 7) | (b & 127)
                    if b < 128: break
                i += l; continue
            if st & 0x80: run = st; i += 1
            ev = run & 0xF0
            if ev in (0xC0, 0xD0): i += 1; continue
            a, b2 = d[i], d[i+1]; i += 2
            if ev == 0x90 and b2 > 0: notes.append((t, a))
        i = end
    notes.sort()
    return notes
if __name__ == '__main__':
    n = read(sys.argv[1]); print(len(n), [p for _, p in n[:30]])
