import asyncio, json
from playwright.async_api import async_playwright
ARR = json.load(open('arr.json'))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('http://localhost:8767/index.html'); await pg.wait_for_timeout(1500)
        sc = await pg.evaluate("""async (arr) => {
          const M = await import('/js/compose/model.js');
          const order = ['flute', 'oboe', 'clarinet', 'bassoon', 'horn', 'trumpet', 'timpani', 'violin1', 'violin2', 'violas', 'cellos', 'contrabasses'];
          const sc = M.newScore({ title: 'Jupiter', composer: 'Gustav Holst', insts: order, time: [3, 4], key: -3, bpm: 76, bars: 25 });
          sc.subtitle = 'from The Planets (the big tune), for orchestra';
          sc.measures[0].tempo = { bpm: 76, beat: 4, text: 'Andante maestoso' };
          M.setPickup(sc, 480);
          const dynAt = { flute: [[16, 'f']], oboe: [[9, 'mf'], [17, 'f']], clarinet: [[9, 'mf'], [17, 'f']], bassoon: [[9, 'mf'], [17, 'f']], horn: [[0, 'mf'], [17, 'f']], trumpet: [[16, 'f']], timpani: [[17, 'f']], violin1: [[0, 'mf'], [17, 'f']], violin2: [[0, 'mf'], [17, 'f']], violas: [[0, 'mf'], [17, 'f']], cellos: [[0, 'mf'], [17, 'f']], contrabasses: [[0, 'mf'], [17, 'f']] };
          order.forEach((k, pi) => {
            const st = sc.parts[pi].staves[0]; const bars = arr.parts[k];
            const want = new Map(dynAt[k]);
            bars.forEach((evs, m) => {
              const len = m === 0 ? 480 : 1440;
              if (evs.length === 1 && evs[0][2] === null && m > 0) { st.bars[m] = M.restBar([3, 4]); return; }
              let dynDone = !want.has(m);
              st.bars[m] = evs.map(([pos, dur, n]) => {
                const v = M.valueOf(dur); if (!v) throw new Error('value ' + dur + ' ' + k + ' ' + m);
                const ev = { id: M.newId(), t: v.t, dots: v.dots };
                if (n === null) { ev.rest = true; return ev; }
                ev.notes = [M.spell(n, -3)];
                if (!dynDone) { ev.dyn = want.get(m); dynDone = true; }
                if (m === 24) ev.art = ['ferm'];
                return ev;
              });
            });
          });
          sc.measures[24].bar = 'final';
          return sc;
        }""", ARR)
        json.dump(sc, open('/home/claude/holst/holst-jupiter.json', 'w'), separators=(',', ':'))
        print('saved', len(json.dumps(sc)), 'bytes', len(sc['measures']), 'bars')
        await b.close()
asyncio.run(main())
