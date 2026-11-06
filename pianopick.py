# Find a Score: the piano accompaniment shown as its own pick (a piano part, the full score of a
# sonata, a concerto's piano reduction) and never an orchestra's piano part
import asyncio, json, os, urllib.parse as U
from playwright.async_api import async_playwright
def F(idx, label, dl, pages=10): return f'<div id="IMSLP{idx}"><a class="internal" href="/images/x/PMLP{idx}-f.pdf">f</a><span class="we_file_download"><a href="#"><span title="dl">{label}</span></a></span><span title="Total number of downloads: {dl}">1</span><span class="we_file_info2">{pages} pp. 1.2 MB</span></div>'
def WE(files, ed=''): return f'<div class="we"><table class="we_edition_info"><tr><th>Editor</th><td>{ed or "First edition"}</td></tr></table>{files}</div>'
GEN = lambda instr: f'<table class="wi_body"><tr><th>Instrumentation</th><td>{instr}</td></tr></table>'
WORKS = {
  'Cello Sonata No.1, Op.38 (Brahms, Johannes)': GEN('cello, piano') + '<div id="tabScore1">' + WE(F(1, 'Complete Score', 9000, 30)) + WE(F(2, 'Complete Score', 3000, 30)) + '</div><div id="tabScore2">' + WE(F(3, 'Cello', 7000, 8)) + '</div>',
  'Cello Concerto, Op.85 (Elgar, Edward)': GEN('cello, orchestra') + '<div id="tabScore1">' + WE(F(10, 'Complete Score', 5000, 80)) + '</div><div id="tabScore2">' + WE(F(11, 'Violoncello solo', 4000) + F(12, 'Piano', 300) + F(13, 'Violin I', 200)) + '</div><div id="tabArrTrans"><h3>For Cello and Piano (Elgar)</h3>' + WE(F(14, 'Piano Score', 6000, 30) + F(15, 'Cello Part', 3000, 8)) + '<h3>For Piano 4 hands (Anon)</h3>' + WE(F(16, 'Complete Score', 9999, 20)) + '</div>',
  'Après un rêve, Op.7 No.1 (Fauré, Gabriel)': GEN('voice, piano') + '<div id="tabScore1">' + WE(F(20, 'Complete Score', 4000, 3)) + '</div><div id="tabScore2">' + WE(F(21, 'Cello', 2500, 1) + F(22, 'Piano', 1800, 3)) + '</div>',
  'Suite for Cello No.1, BWV 1007 (Bach, Johann Sebastian)': GEN('cello') + '<div id="tabScore1">' + WE(F(30, 'Complete Score', 99000, 6)) + '</div>',
}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script("window.__noTour = true;")
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            q = dict(U.parse_qsl(U.urlparse(route.request.url).query)); cb = q['callback']
            if q.get('action') == 'parse': d = {'parse': {'title': q['page'], 'text': {'*': WORKS[q['page']]}}}
            elif q.get('list') == 'categorymembers': d = {'query': {'categorymembers': [{'title': t} for t in WORKS]}}
            else: d = {'query': {'search': [{'title': t, 'snippet': ''} for t in WORKS]}}
            await route.fulfill(content_type='text/javascript', body=f'{cb}({json.dumps(d)})')
        await pg.route('https://imslp.org/api.php*', api)
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const s = document.querySelector('#welInst'); if (s) { s.value = 'cello'; s.dispatchEvent(new Event('change')); } document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(900)
        res = {}
        for t in WORKS:
            got = await pg.evaluate("""async (t) => { const I = await import('/js/imslp.js'); const d = await I.workFiles(t); const r = I.rankFiles(d.files, ['cello', 'violoncello', 'vc'], d.title + ' ' + (d.instr || '')); return r.picks.map((p) => [p.why, p.pianoKind || '', p.f.label, p.f.index]); }""", t)
            res[t] = got; print(t, got)
            if 'Elgar' in t: print(await pg.evaluate("async (t) => { const I = await import('/js/imslp.js'); const d = await I.workFiles(t); return d.files.map((f) => [f.group, f.label, f.heading]); }", t))
        pf = lambda t: [x for x in res[t] if x[0] == 'piano']
        ok = (pf('Cello Sonata No.1, Op.38 (Brahms, Johannes)') == [['piano', 'score', 'Complete Score', '1']]
              and pf('Cello Concerto, Op.85 (Elgar, Edward)') == [['piano', 'reduction', 'Piano Score', '14']]
              and pf('Après un rêve, Op.7 No.1 (Fauré, Gabriel)') == [['piano', 'part', 'Piano', '22']]
              and pf('Suite for Cello No.1, BWV 1007 (Bach, Johann Sebastian)') == [])
        # a pianist gets no accompaniment pick
        pn = await pg.evaluate("""async () => { const I = await import('/js/imslp.js'); const d = await I.workFiles('Cello Sonata No.1, Op.38 (Brahms, Johannes)'); return I.rankFiles(d.files, ['piano'], d.title + ' ' + d.instr).picks.map((p) => p.why); }""")
        ok = ok and 'piano' not in pn
        # the page itself
        await pg.evaluate("() => { [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Find a score')?.click(); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const i = document.querySelector('#findInput'); i.value = 'elgar cello concerto'; document.querySelector('#findForm').requestSubmit(); }"); await pg.wait_for_timeout(1800)
        await pg.evaluate("() => [...document.querySelectorAll('#workList button')].find((b) => /Concerto/.test(b.textContent)).click()"); await pg.wait_for_timeout(1500)
        cards = await pg.evaluate("() => [...document.querySelectorAll('#workPicks .pick')].map((c) => c.querySelector('.why').textContent + ' | ' + c.querySelector('.pl').textContent + ' | ' + c.querySelector('.pm').textContent)")
        print('\n'.join(cards))
        await pg.evaluate("() => document.querySelector('#workPicks').scrollIntoView({ block: 'center' })"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/tmp/claude-0/fz/pianopick.png')
        ok = ok and any(c.startswith('Piano accompaniment | Piano Score | Piano reduction') for c in cards)
        print('PASS' if ok else 'FAIL', 'piano accompaniment pick'); print(errs[:3])
        await b.close()
asyncio.run(main())
