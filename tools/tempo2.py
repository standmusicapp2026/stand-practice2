# (tempo2) Metronome marks: the metronome counts the note the mark names at the number printed
# (𝅗𝅥 = 132 → 132 half notes in 2/2; ♩. = 60 → 60, each in three; ♪ = 120 → 60 in two), and on a
# scanned page the note drawn before "=" is looked at (hollow head: half; filled: quarter; flag:
# eighth; a dot: dotted), whatever the reader took it for.
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async () => {
          const T = await import('/js/tempo.js');
          const mf = (bpm, u, m) => JSON.stringify(T.metroFor(bpm, u, m));
          const metro = { half44: mf(132, 2, '4/4'), q44: mf(120, 1, '4/4'), dq68: mf(60, 1.5, '6/8'), dq44: mf(60, 1.5, '4/4'), e44: mf(120, 0.5, '4/4'), q22: mf(100, 1, '2/2'), half34: mf(60, 2, '3/4') };
          // a scanned mark: "J = 132" with the note drawn as on a page (head, stem, maybe flag or dot)
          const draw = (kind) => {
            const c = document.createElement('canvas'); c.width = 600; c.height = 200; const g = c.getContext('2d');
            g.fillStyle = '#f2efe8'; g.fillRect(0, 0, 600, 200); g.fillStyle = '#222'; g.strokeStyle = '#222';
            const hx = 100, hy = 120;
            g.save(); g.translate(hx, hy); g.rotate(-0.4); g.beginPath(); g.ellipse(0, 0, 13, 9, 0, 0, Math.PI * 2);
            if (kind.startsWith('half')) { g.lineWidth = 3.5; g.stroke(); } else g.fill(); g.restore();
            g.fillRect(hx + 10, hy - 62, 3, 62);
            if (kind === 'eighth') { g.beginPath(); g.moveTo(hx + 13, hy - 62); g.quadraticCurveTo(hx + 34, hy - 38, hx + 30, hy - 18); g.lineWidth = 4; g.stroke(); }
            if (kind.endsWith('dot')) { g.beginPath(); g.arc(hx + 26, hy, 4, 0, Math.PI * 2); g.fill(); }
            g.font = '44px serif'; g.fillText('=', 150, 135); g.fillText('132', 195, 135);
            return c;
          };
          const m = { x: 80 / 600, y: 95 / 200, w: (300 - 80) / 600, h: 45 / 200, text: 'J = 132', exact: true, bpm: 132 };
          const seen = {}; for (const k of ['half', 'quarter', 'eighth', 'quarter-dot', 'half-dot']) seen[k] = T.noteOfMark(draw(k), m);
          return { metro, seen };
        }""")
        print(json.dumps(r, ensure_ascii=False))
        mt = {k: json.loads(v) for k, v in r['metro'].items()}
        ok = mt['half44'] == {'bpm': 132, 'meter': '2/2'} and mt['q44'] == {'bpm': 120} and mt['dq68'] == {'bpm': 60, 'meter': '2/8', 'sub': 3} or True
        ok = (mt['half44'] == {'bpm': 132, 'meter': '2/2'} and mt['q44'] == {'bpm': 120} and mt['dq68']['bpm'] == 60 and mt['dq68'].get('sub') == 3
              and mt['e44'] == {'bpm': 60, 'sub': 2} and mt['q22'] == {'bpm': 100, 'meter': '4/4'}
              and r['seen'] == {'half': 2, 'quarter': 1, 'eighth': 0.5, 'quarter-dot': 1.5, 'half-dot': 3})
        print('PASS' if ok and not errs else 'FAIL', 'metronome marks: the printed note at the printed number', errs[:2])
        await b.close()
asyncio.run(main())
