// Stand's self-test, run inside the real app (iOS Simulator, WKWebView) when it is started with
// -standSelfTest. Only in the simulator test build: this file is not part of the app sent out.
// Each step writes "SELFTEST ok|FAIL <step> <detail>" to the events log (Files › Stand › Diagnostics);
// "SHOT <name>" asks the test machine for a screenshot (it waits 2.5 s for it).
const $ = (q) => document.querySelector(q), $$ = (q) => [...document.querySelectorAll(q)];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const say = (t) => { try { window.webkit.messageHandlers.standDiag.postMessage({ op: 'log', text: String(t).slice(0, 290) }); } catch {} };
const R = { ok: 0, fail: 0 };
const waitFor = async (fn, ms = 15000) => { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch {} await sleep(150); } return null; };
const shot = async (name) => { say('SHOT ' + name); await sleep(2600); };
async function step(name, fn, ms = 40000) {
  const t0 = Date.now();
  try {
    const r = await Promise.race([fn(), sleep(ms).then(() => { throw new Error('took more than ' + ms / 1000 + ' s'); })]);
    if (r === false) throw new Error('check failed');
    R.ok++; say(`SELFTEST ok ${name} ${Date.now() - t0}ms ${typeof r === 'string' ? r : ''}`);
  } catch (e) { R.fail++; say(`SELFTEST FAIL ${name} ${(e && e.message) || e}`); }
}
const ptr = (t, type, x, y, id, kind, extra = {}) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: id, pointerType: kind, isPrimary: true, clientX: x, clientY: y, pressure: 0.5, width: kind === 'touch' ? 30 : 1, height: kind === 'touch' ? 30 : 1, buttons: type === 'pointerup' ? 0 : 1, ...extra }));
async function stroke(kind = 'pen', fx = 0.4, fy = 0.4) {
  const t = $('#stage'), pg = $('#stage .pg'); const r = (pg || t).getBoundingClientRect();
  let x = r.left + r.width * fx, y = r.top + r.height * fy;
  ptr(t, 'pointerdown', x, y, 31, kind);
  for (let i = 0; i < 16; i++) { x += 6; y += (i % 2 ? 3 : -3); ptr(t, 'pointermove', x, y, 31, kind); await sleep(12); }
  ptr(t, 'pointerup', x, y, 31, kind);
}
const key = (k) => (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, bubbles: true }));
const closePanels = async () => { for (const b of $$('aside.panel:not([hidden]) [data-close]')) b.click(); await sleep(400); };
const home = async () => { await closePanels(); if (!$('#score').hidden) $('#backBtn').click(); if (!$('#compose').hidden) $('#cpBack').click(); await waitFor(() => !$('#library').hidden, 15000); await sleep(600); };

async function run() {
  say(`SELFTEST start ${navigator.userAgent} screen ${screen.width}x${screen.height}@${devicePixelRatio} window ${innerWidth}x${innerHeight}`);
  await waitFor(() => window.__standUp, 20000);
  await sleep(1500);
  await step('start', async () => { $('#welGo') && $('#welGo').click(); await sleep(600); $('.tour-skip') && $('.tour-skip').click(); await sleep(400); return !!window.__standUp; });
  await shot('01-home');
  if (document.body.classList.contains('phone')) return phoneRun();
  // the sample score from the empty library (the first thing a new musician may tap)
  await step('sample score', async () => {
    const b = $('#sampleBtn'); if (!b || !b.offsetParent) return 'no empty library here';
    b.click();
    return !!(await waitFor(() => !$('#score').hidden && $$('#stage canvas.art').length && $$('#stage canvas.art').every((c) => c.width > 10), 30000));
  });
  await shot('01b-sample');
  await home();
  await step('import a PDF', async () => {
    const buf = await (await fetch('_selftest/vector8.pdf')).arrayBuffer();
    const f = new File([buf], 'Cello Suite selftest.pdf', { type: 'application/pdf' });
    const dt = new DataTransfer(); dt.items.add(f);
    // (the sample score may already be in the library: wait for one more card, this one)
    const n0 = $$('#grid .card:not(.folder)').length;
    const inp = $('#importInput'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true }));
    return !!(await waitFor(() => $$('#grid .card:not(.folder)').length >= n0 + 1, 30000));
  });
  await shot('02-library');
  await step('open the score', async () => {
    const cards = $$('#grid .card:not(.folder)'); (cards.find((c) => /selftest|Cello Suite No\. 1\b/i.test(c.textContent)) || cards[0]).click();
    return !!(await waitFor(() => $$('#stage canvas.art').length && $$('#stage canvas.art').every((c) => c.width > 10), 20000));
  });
  await shot('03-score');
  await step('turn pages with the pedal keys', async () => {
    const before = $('#pageNum') ? $('#pageNum').textContent : '';
    for (let i = 0; i < 4; i++) { key('ArrowRight'); await sleep(500); }
    for (let i = 0; i < 4; i++) { key('ArrowLeft'); await sleep(300); }
    return 'pages ' + before;
  });
  await step('write with the Pencil', async () => {
    // (each part timed: a slow simulator and a real stall look different here)
    const T = [], t0 = performance.now(), mark = (w) => T.push(w + ' ' + Math.round(performance.now() - t0));
    $('#inkBtn') && $('#inkBtn').click(); await sleep(500); mark('tools');
    await stroke('pen', 0.3, 0.3); mark('stroke1'); await sleep(300); await stroke('pen', 0.3, 0.5); mark('stroke2'); await sleep(2500); mark('wait');
    const { db } = await import('./db.js'); mark('import');
    // (a timer beside the database read: does the page still run while it waits?)
    let ticks = 0; const tk = setInterval(() => { ticks++; if (ticks % 25 === 0) say('SELFTEST pencil: database read still waiting, page alive ' + T.join(', ')); }, 200);
    const keys = await db.keys('ink'); clearInterval(tk); mark('keys');
    say('SELFTEST pencil timings ' + T.join(', '));
    return keys.length > 0 ? keys.length + ' pages with markings' : false;
  });
  await shot('04-writing');
  await step('zoom with two fingers', async () => {
    const t = $('#stage'), r = t.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    ptr(t, 'pointerdown', cx - 50, cy, 41, 'touch'); ptr(t, 'pointerdown', cx + 50, cy, 42, 'touch', { isPrimary: false });
    for (let i = 1; i <= 10; i++) { ptr(t, 'pointermove', cx - 50 - i * 15, cy, 41, 'touch'); ptr(t, 'pointermove', cx + 50 + i * 15, cy, 42, 'touch', { isPrimary: false }); await sleep(20); }
    ptr(t, 'pointerup', cx - 200, cy, 41, 'touch'); ptr(t, 'pointerup', cx + 200, cy, 42, 'touch', { isPrimary: false });
    await sleep(800); const pill = $('.zoom-pill'); return pill && !pill.hidden ? pill.textContent : false;
  });
  await shot('05-zoom');
  await step('zoom back', async () => { const pill = $('.zoom-pill'); if (pill && !pill.hidden) pill.click(); await sleep(500); return true; });
  await step('Pages panel', async () => {
    $('#score [data-panel=settings]').click(); await sleep(400);
    const b = $('#pagesBtn, [data-panel="pages"], #pgOpen'); if (b) b.click(); await sleep(1500);
    return !$('#panel-pages').hidden && $$('#pageGrid .pcell').length >= 8;
  });
  await shot('06-pages');
  await step('metronome', async () => {
    await closePanels(); $('#score [data-panel=metronome]').click(); await sleep(500); $('#metroToggle').click(); await sleep(1500);
    return !$('#metroPill').hidden || $('#metroToggle').textContent.includes('Stop');
  });
  await shot('07-metronome');
  await step('metronome off', async () => { $('#metroToggle').click(); await sleep(400); await closePanels(); return true; });
  await step('tuner', async () => { $('#score [data-panel=tuner]').click(); await sleep(2500); return !$('#panel-tuner').hidden; });
  await shot('08-tuner');
  await step('back home', async () => { await home(); return !$('#library').hidden; });
  await step('notebook', async () => {
    $('#newNotebookBtn').click(); await sleep(1500); $('#nbCreate').click();
    await waitFor(() => !$('#score').hidden && $$('#stage .pg').length, 15000); await sleep(1200);
    $('.tour-skip') && $('.tour-skip').click(); await sleep(300);
    await stroke('pen', 0.3, 0.3); await sleep(600); return true;
  });
  await shot('09-notebook');
  await step('back home 2', async () => { await home(); return !$('#library').hidden; });
  await step('Compose', async () => {
    const E = await import('./compose/editor.js');
    await E.createComposition({ title: 'Selftest', insts: ['cello', 'piano'], time: [4, 4], bars: 8 });
    await sleep(2000); $('.tour-skip') && $('.tour-skip').click(); await sleep(300);
    return !$('#compose').hidden && $$('#compose canvas').length > 0;
  });
  await shot('10-compose');
  await step('back home 3', async () => { await home(); return !$('#library').hidden; });
  await step('Compose example (Holst, orchestra)', async () => {
    $('[data-panel=compose]').click(); await sleep(800); $('.tour-skip') && $('.tour-skip').click();
    $('#cnExample').click();
    return !!(await waitFor(() => !$('#compose').hidden && $$('#compose canvas').length > 0, 20000));
  });
  await shot('10b-jupiter');
  await step('back home 4', async () => { await home(); return !$('#library').hidden; });
  await step('settings', async () => { $('[data-panel=app]').click(); await sleep(800); return !$('#panel-app').hidden; });
  await shot('11-settings');
  // linking a device: the card in Settings, and the linking screen (looking; nothing nearby here)
  await step('linked devices card', async () => { const c = $('#pairCard'); if (c) c.scrollIntoView(); await sleep(600); return !!c && !c.hidden; });
  await shot('11b-linked-devices');
  await step('linking screen', async () => { $('#pairNew').click(); await sleep(1500); return !!$('.pair') && !$('.pair .pair-find').hidden; });
  await shot('11c-linking');
  await step('linking screen closes', async () => { const c = [...$$('.pair .btn')].find((b) => /Cancel/.test(b.textContent)); c && c.click(); await sleep(500); return !$('.pair'); });
  await step('backup panel', async () => { await closePanels(); const b = $('[data-panel=backup]'); if (b) b.click(); await sleep(1200); return true; });
  await shot('12-backup');
  await closePanels();
  // the score again after all that, then many quick turns (memory)
  await step('many quick turns', async () => {
    $('#grid .card:not(.folder)') && [...$$('#grid .card:not(.folder)')].find((c) => /Cello|selftest/i.test(c.textContent))?.click();
    await waitFor(() => !$('#score').hidden, 10000); await sleep(1500);
    for (let i = 0; i < 60; i++) { key(i % 16 < 8 ? 'ArrowRight' : 'ArrowLeft'); await sleep(120); }
    await sleep(1000); return true;
  });
  await shot('13-after-turns');
  await home();
  for (const e of (window.__standErrors || [])) say('SELFTEST error ' + e.line);
  say(`SELFTEST DONE ok=${R.ok} fail=${R.fail} errors=${(window.__standErrors || []).length}`);
}
// the iPhone: its own home, the tools in the pocket, the linking screen, sideways and back
async function phoneRun() {
  // (a new iPhone first asks about linking an iPad: answered "Not now", as most would at first)
  await step('iPhone: link question answered', async () => { const nb = await waitFor(() => [...$$('.ask-back button')].find((b) => /Not now/.test(b.textContent)), 5000); if (!nb) return 'not asked'; nb.click(); await sleep(500); return ![...$$('.ask-back')].length; });
  const open = async (p) => { const b = $$(`[data-panel=${p}]`).find((x) => x.offsetParent) || $(`[data-panel=${p}]`); b && b.click(); await sleep(900); $('.tour-skip') && $('.tour-skip').click(); await sleep(200); return !$('#panel-' + p).hidden; };
  for (const p of ['tuner', 'metronome', 'scales', 'record', 'takes', 'app']) {
    await step('iPhone: ' + p, async () => open(p));
    await shot('p-' + p);
    await closePanels();
  }
  await step('iPhone: metronome plays', async () => { await open('metronome'); $('#metroToggle').click(); await sleep(2500); $('#metroToggle').click(); await sleep(300); await closePanels(); return true; });
  await step('iPhone: linking screen', async () => { await open('app'); const c = $('#pairCard'); c && c.scrollIntoView(); await sleep(400); const n = $('#pairNew'); if (!n) return 'no button'; n.click(); await sleep(1500); const ok = !!$('.pair'); const x = [...$$('.pair .btn')].find((b) => /Cancel/.test(b.textContent)); x && x.click(); await sleep(400); await closePanels(); return ok; });
  await shot('p-end');
  for (const e of (window.__standErrors || [])) say('SELFTEST error ' + e.line);
  say(`SELFTEST DONE ok=${R.ok} fail=${R.fail} errors=${(window.__standErrors || []).length}`);
}
run().catch((e) => say('SELFTEST FAIL run ' + ((e && e.message) || e)));
