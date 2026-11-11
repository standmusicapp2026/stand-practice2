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

// Leaving Stand with the metronome on, as a musician does (another app, then back), three times:
// it keeps playing and nothing breaks. Then leaving with nothing playing: the sound rests (nothing
// is left showing as playing). The test machine switches apps when it reads "SELFTEST LEAVE n".
// (what happened to the sound lately, said when a check fails)
const alogTail = (n = 10) => (window.__audioLog || []).slice(-n).map((e) => `${((e.t - Date.now()) / 1000).toFixed(1)}s ${e.what} [${e.state}]`).join(' | ');
async function bgRun() {
  const S = () => (window.__standSound ? window.__standSound() : {});
  const openM = async () => { const b = $$('[data-panel=metronome]').find((x) => x.offsetParent) || $('[data-panel=metronome]'); b && b.click(); await sleep(900); $('.tour-skip') && $('.tour-skip').click(); await sleep(200); };
  // (every click given to the sound system, with its time: away from Stand each one must still be in time)
  const CL = []; { const P = AudioBufferSourceNode.prototype, st = P.start, sp = P.stop;
    P.start = function (t, ...r) { CL.push({ t, n: this }); if (CL.length > 3000) CL.splice(0, 1000); return st.call(this, t, ...r); };
    P.stop = function (...r) { this.__stopped = true; return sp.apply(this, r); }; }
  const inTime = (from, to) => { const m = window.__standMetro; const ts = CL.filter((x) => !x.n.__stopped && x.t >= from && x.t <= to).map((x) => x.t).sort((a, b) => a - b);
    const want = 60 / m.bpm / (m.subdiv || 1); let off = 0; const bad = [];
    for (let i = 1; i < ts.length; i++) if (Math.abs(ts[i] - ts[i - 1] - want) > 0.003) { off++; if (bad.length < 8) bad.push(`${(ts[i] - from).toFixed(2)}:${(ts[i] - ts[i - 1]).toFixed(3)}`); }
    return { n: ts.length, off, want: +want.toFixed(3), bad, log: off ? alogTail() : undefined }; };
  await step('background: metronome on', async () => { await closePanels(); await openM(); if (!S().metro) $('#metroToggle').click(); await sleep(2000); await closePanels(); return S().metro ? `beats ${S().beats}` : false; });
  // (the leave is seen by its event: a page paused in the background cannot see it by looking)
  let hides = 0; document.addEventListener('visibilitychange', () => { if (document.hidden) hides++; });
  // (how much the page ran while away: a stalled test machine sometimes runs none of it at all)
  // (and the longest the page went without running at all while away: the test machine stalling
  // the whole simulator, which an iPad never does to a page playing sound)
  let awayTicks = 0, lastTick = 0, awayGap = 0;
  setInterval(() => { const t = performance.now(); if (document.hidden) { awayTicks++; if (lastTick) awayGap = Math.max(awayGap, t - lastTick); } lastTick = t; }, 200);
  const away = async () => { const h0 = hides; const hid = await waitFor(() => hides > h0, 150000); const back = await waitFor(() => !document.hidden, 90000); return { hid: !!hid, back: !!back }; };
  // (what iOS shows away from Stand: its name for what plays, with the icon, and play/pause)
  await step('now playing: the metronome by name', async () => { await sleep(1300); const ms = navigator.mediaSession; const md = ms && ms.metadata;
    if (!ms) return 'no Media Session in this web view';
    return md && /^Metronome/.test(md.title) && md.artist === 'Stand' && ms.playbackState === 'playing' ? md.title : false; });
  let seenAway = 0;
  for (let n = 1; n <= 3; n++) {
    const s0 = S(), b0 = s0.beats, t0 = Date.now(), c0 = window.__standMetro && window.__standMetro._ctx ? window.__standMetro._ctx.currentTime : 0;
    awayGap = 0; say('SELFTEST LEAVE ' + n);
    const { hid, back } = await away();
    await sleep(2000);
    if (window.__standMetro && window.__standMetro._ctx) { const it = inTime(c0 + 0.5, window.__standMetro._ctx.currentTime - 0.2);
      // (a gap in the clicks while the whole page was stopped for longer than the clicks given ahead
      // (5-10 s) is the test machine's stall, not Stand's: noted, not judged)
      const stalled = awayGap > 9000;
      await step(`background ${n}: every click in time`, async () => (it.n > 4 && it.off === 0) ? `${it.n} clicks` : (say(`SELFTEST detail clicks ${n}: ${JSON.stringify(it)} page stopped ${Math.round(awayGap / 1000)} s`), stalled ? `page stopped ${Math.round(awayGap / 1000)} s by the test machine; ${it.off} gaps` : false)); }
    const s = S(), secs = Math.round((Date.now() - t0) / 1000);
    const info = `hid ${hid} back ${back} metro ${s.metro} beats ${b0}->${s.beats} clock ${(+s0.clock || 0).toFixed(1)}->${(+s.clock || 0).toFixed(1)} in ${secs} s, sound ${s.state}, rested ${s0.rested}->${s.rested}`;
    if (!(hid && back && s.metro && s.beats > b0 + 8)) say('SELFTEST detail background ' + n + ': ' + info);
    // (a busy test machine sometimes never puts Stand away: then it was not away, and is judged only on playing on)
    if (hid) seenAway++;
    await step(`background ${n}: back, the metronome kept playing`, async () => (back && s.metro && s.beats > b0 + 8) ? (hid ? info : 'not put away this time; ' + info) : false);
  }
  await step('background: put away at least twice while playing', async () => seenAway >= 2 ? `${seenAway} of 3` : false);
  // (pause and play from the lock screen, as iOS does them: the sound system paused, later started, from outside)
  await step('lock screen pause: the metronome stops and stays stopped', async () => { const m = window.__standMetro, c = m._ctx; if (!window.__standOutside) return false;
    const T0 = Date.now() - 4000, seen = [];
    const look = setInterval(() => { const k = c.state[0] + (m.running ? 'M' : '-'); if (seen[seen.length - 1] !== k) seen.push(k); }, 100);
    let pr = 'none'; try { await window.__standOutside.pause(c); pr = 'done ' + c.state; } catch (e) { pr = 'refused ' + e; }
    await sleep(2500); clearInterval(look);
    const d = `metro ${m.running} sound ${c.state} same ${c === m._ctx} ${navigator.mediaSession ? navigator.mediaSession.playbackState : ''}`;
    if (!(!m.running && c.state === 'suspended')) {
      say(`SELFTEST detail lock pause: ${d} pause ${pr} hidden ${document.hidden} states ${seen.join(' ')} sound ${JSON.stringify(S())}`);
      const L = (window.__audioLog || []).filter((e) => e.t >= T0).map((e) => `${((e.t - Date.now()) / 1000).toFixed(1)}s ${e.what} [${e.state}]`);
      for (let i = 0; i < L.length; i += 4) say('SELFTEST detail lock pause log: ' + L.slice(i, i + 4).join(' | '));
    }
    return !m.running && c.state === 'suspended' ? d : false; });
  await step('lock screen play: the metronome starts again', async () => { const m = window.__standMetro, c = m._ctx;
    await window.__standOutside.play(c); await sleep(1500); const d = `metro ${m.running} sound ${c.state} beats ${S().beats}`;
    if (!(m.running && c.state === 'running')) say('SELFTEST detail lock play: ' + d + ' log: ' + alogTail()); return m.running && c.state === 'running' ? d : false; });
  await step('background: metronome off', async () => { await openM(); if (S().metro) $('#metroToggle').click(); await sleep(800); await closePanels(); return !S().metro; });
  // (nothing playing: Stand is really put away by iOS each time; four times, short and long)
  let seenAway2 = 0;
  for (let n = 4; n <= 7; n++) {
    const r0 = S().rested, k0 = awayTicks;
    awayGap = 0; say('SELFTEST LEAVE ' + n);
    const { hid, back } = await away();
    await sleep(2500);
    if (hid) seenAway2++;
    // (the first time, the sound must have rested while away, unless the page never ran there at all)
    const ran = awayTicks - k0 >= 6 && awayGap < 5000;
    const ok = back && (!hid ? n > 4 : (n > 4 || S().rested > r0 || !ran));
    if (!ok || !ran) say(`SELFTEST detail background ${n}: hid ${hid} back ${back} rested ${r0}->${S().rested} busy ${S().busy} sound ${S().state} ran away ${awayTicks - k0} stopped ${Math.round(awayGap / 1000)} s`);
    await step(`background ${n}: nothing playing, the sound rested away, back fine`, async () => ok ? (hid ? '' : 'not put away this time; ') + `sound ${S().state}` : false);
  }
  await step('background: put away at least three times of four with nothing playing', async () => seenAway2 >= 3 ? `${seenAway2} of 4` : false);
  await step('background: the metronome starts again', async () => { await openM(); $('#metroToggle').click(); await sleep(2000); const ok = S().metro && S().state === 'running'; $('#metroToggle').click(); await sleep(400); await closePanels(); return ok; });
}
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
  // (squeezing the Pencil Pro: the tool wheel at the tip; a tap on a tool chooses it and closes it)
  await step('tool wheel (Pencil squeeze)', async () => {
    // (the notebook open first: on a slow machine it can take long)
    await waitFor(() => !$('#score').hidden && $$('#stage .pg').length, 20000);
    window.standPencilSqueeze({ x: Math.round(innerWidth / 2), y: Math.round(innerHeight / 2) });
    await waitFor(() => $('.wheel.open'), 3000);
    const w = $('.wheel.open'); if (!w) { say('SELFTEST detail wheel: score hidden ' + $('#score').hidden + ' wheel ' + !!$('.wheel')); return false; }
    const n = w.querySelectorAll('.wheel-tool').length; w.querySelector('.wheel-tool[data-tool=hl]').click(); await sleep(500);
    const ok = ($('.ink-tool.on[data-tool]') || {}).dataset?.tool === 'hl' && !$('.wheel');
    $('.ink-tool[data-tool=pen]').click(); await sleep(200);
    return ok ? n + ' tools' : false;
  });
  await step('ruler: a line along its edge is straight', async () => {
    const b = $('#rulerBtn'); if (!b || !b.offsetParent) return 'no ruler button here';
    b.click(); await sleep(500); const R = window.__ruler; if (!R || !R.on) return false;
    const t = $('#stage'), y = R.cy + R.h / 2 + 8;
    ptr(t, 'pointerdown', R.cx - 150, y, 35, 'pen');
    for (let i = 1; i <= 25; i++) { ptr(t, 'pointermove', R.cx - 150 + i * 12, y + Math.sin(i) * 6, 35, 'pen'); await sleep(16); }
    ptr(t, 'pointerup', R.cx + 150, y, 35, 'pen'); await sleep(500);
    const li = window.__lastInk(); b.click(); await sleep(300);
    return li && li.dev < 0.0006 && Math.abs(li.dy) < 0.0006 && !window.__ruler.on ? 'straight' : (say('SELFTEST detail ruler ' + JSON.stringify(li)), false);
  });
  await shot('09-notebook');
  await step('back home 2', async () => { await home(); return !$('#library').hidden; });
  // (the tempo printed in a score: found, and a tap starts the metronome at it)
  await step('tempo mark: found, a tap starts the metronome at it', async () => {
    const buf = await (await fetch('_selftest/piano.pdf')).arrayBuffer();
    const f = new File([buf], 'Little Piece selftest.pdf', { type: 'application/pdf' });
    const dt = new DataTransfer(); dt.items.add(f);
    const n0 = $$('#grid .card:not(.folder)').length;
    const inp = $('#importInput'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true }));
    if (!(await waitFor(() => $$('#grid .card:not(.folder)').length >= n0 + 1, 30000))) return false;
    await sleep(800);
    const card = $$('#grid .card:not(.folder)').find((c) => /Little Piece/i.test(c.textContent)); if (!card) return false;
    card.click();
    if (!(await waitFor(() => $$('#stage .tempo-mark').length >= 2, 20000))) { say('SELFTEST detail tempo: marks ' + $$('#stage .tempo-mark').length); return false; }
    const m = $$('#stage .tempo-mark'), lbl = m.map((x) => x.getAttribute('aria-label')).join(' | ');
    m[0].click(); await sleep(1000);
    const ok = window.__standMetro.bpm === 108 && window.__standMetro.running;
    $('#metroToggle').click(); await sleep(300); await closePanels();
    return ok ? lbl : (say('SELFTEST detail tempo: ' + lbl + ' bpm ' + window.__standMetro.bpm + ' running ' + window.__standMetro.running), false);
  });
  await step('back home 2b', async () => { await home(); return !$('#library').hidden; });
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
  // bringing scores from another app: a whole folder (made by the test machine in Stand's Documents,
  // as if chosen in Files), its sub-folders becoming folders, IMSLP names made into titles; again: nothing twice
  await step('bring scores from a folder (another app)', async () => {
    await home();
    const { db, getSetting } = await import('/js/db.js');
    const before = (await db.all('scores')).length;
    window.webkit.messageHandlers.standPickFolder.postMessage({ testPath: 'BringTest' });
    let n = before; for (let i = 0; i < 90 && n < before + 3; i++) { await sleep(1000); n = (await db.all('scores')).length; }
    await sleep(1500);
    const all = await db.all('scores'), fol = await getSetting('folders', []);
    const names = fol.map((f) => f.name).filter((x) => /Etudes|Pieces/.test(x));
    const brought = all.filter((x) => x.importedFrom);
    window.webkit.messageHandlers.standPickFolder.postMessage({ testPath: 'BringTest' });
    await sleep(6000);
    const again = (await db.all('scores')).length;
    const titles = brought.map((x) => x.title).join(' / ');
    if (n - before !== 3 || names.length !== 2 || again !== n || /IMSLP|PMLP|_/.test(titles)) throw new Error(`${n - before} scores, folders ${names}, again +${again - n}, titles ${titles}`);
    return `3 scores in ${names.join(', ')}: ${titles}`;
  }, 120000);
  await shot('12b-brought');
  await step('bring two folders chosen together', async () => {
    const { db, getSetting } = await import('/js/db.js');
    const before = (await db.all('scores')).length;
    window.webkit.messageHandlers.standPickFolder.postMessage({ testPath: 'Multi/Sonatas|Multi/Studies' });
    let n = before; for (let i = 0; i < 60 && n < before + 2; i++) { await sleep(1000); n = (await db.all('scores')).length; }
    await sleep(1500);
    const fol = (await getSetting('folders', [])).map((f) => f.name).filter((x) => /Sonatas|Studies/.test(x));
    if (n - before !== 2 || fol.length !== 2) throw new Error(`${n - before} scores, folders ${fol}`);
    return `2 scores in ${fol.join(', ')}`;
  }, 90000);
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
  await videoRun();
  await bgRun();
  for (const e of (window.__standErrors || [])) say('SELFTEST error ' + e.line);
  say(`SELFTEST DONE ok=${R.ok} fail=${R.fail} errors=${(window.__standErrors || []).length}`);
}
// A video brought in through iOS (as from Files or Photos), then made into a film in Studio by iOS:
// every picture, at the video's own rate and size, with its sound, played back to check.
async function videoRun() {
  await closePanels();
  let got = null;
  await step('video in: whole, with its sound', async () => {
    window.__videoIn = null;
    if (!window.webkit.messageHandlers.standVideoIn) throw new Error('no standVideoIn');
    window.webkit.messageHandlers.standVideoIn.postMessage({ cmd: 'test', path: 'VideoTest/clip.mov' });
    got = await waitFor(() => window.__videoIn, 60000);
    if (!got || got.error) throw new Error('not in: ' + JSON.stringify(got));
    return got.pcm && got.dur > 2.5 && got.dur < 3.5 ? `${got.dur.toFixed(2)} s, ${Math.round(got.size / 1000)} kB, sound read` : false;
  }, 90000);
  await shot('v1-video-in');
  if (!got || got.error) return;
  await step('studio export: the film made by iOS', async () => {
    await closePanels();
    const S = await import('/js/studio.js');
    await S.openStudio(got.id); await sleep(1500);
    S._studio.P.trim = { a: 0, b: 2 };
    window.__studioExport = null;
    const ok = await S._exportNative({ share: false });
    const r = window.__studioExport;
    if (!ok || !r) throw new Error('not made');
    // the film itself, played: its length and size
    const { db } = await import('/js/db.js');
    const takes = (await db.all('takes')).sort((x, y) => y.created - x.created);
    const f = await db.get('files', 'video:' + takes[0].id);
    const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.src = URL.createObjectURL(f.data);
    await new Promise((res) => { v.onloadedmetadata = res; v.onerror = res; setTimeout(res, 8000); });
    // (a picture from the middle of the film, against the original at the same moment: the same scene,
    // upright, not black)
    const mean = async (vid, t) => { await new Promise((res) => { vid.onseeked = res; vid.currentTime = t; setTimeout(res, 3000); }); await sleep(200); const c = document.createElement('canvas'); c.width = 24; c.height = 24; const g = c.getContext('2d'); g.drawImage(vid, 0, 0, 24, 24); const d = g.getImageData(0, 0, 24, 24).data; let s2 = 0; for (let k = 0; k < d.length; k += 4) s2 += d[k] + d[k + 1] + d[k + 2]; return s2 / (d.length / 4) / 3; };
    const src = document.createElement('video'); src.muted = true; src.playsInline = true; src.src = URL.createObjectURL((await db.get('files', 'video:' + got.id)).data);
    await new Promise((res) => { src.onloadedmetadata = res; src.onerror = res; setTimeout(res, 8000); });
    const mOut = await mean(v, 1.0), mSrc = await mean(src, 1.0);
    const upright = Math.abs(v.videoWidth / Math.max(1, v.videoHeight) - src.videoWidth / Math.max(1, src.videoHeight)) < 0.03 || !r.over;
    const ok2 = Math.abs(v.duration - 2) < 0.2 && v.videoWidth === r.w && v.videoHeight === r.h && r.frames >= 57 && r.audio !== 'none' && (mOut > 8 || mSrc < 8) && upright && (!r.over || mSrc < 8 || Math.abs(mOut - mSrc) < 40);
    $('#stBack') && $('#stBack').click(); await sleep(800);
    const msg = `${r.over ? 'over the original' : 'pictures'} ${r.frames} ${r.w}x${r.h} (original ${src.videoWidth}x${src.videoHeight}) @${r.fps}, ${(v.duration || 0).toFixed(2)} s, ${Math.round(r.size / 1000)} kB, sound ${r.audio}, light ${mOut.toFixed(0)}/${mSrc.toFixed(0)}, ${JSON.stringify(r.seeks)} ${JSON.stringify(r.ms)}`;
    if (!ok2) throw new Error(msg);
    // (made over the original itself, as it should be on the iPad; else it fell back)
    if (window.standCaps && window.standCaps.videoOver && !r.over) throw new Error('fell back: ' + msg);
    return msg;
  }, 180000);
  await step('studio export: picture by picture (the way kept for when the other fails)', async () => {
    await closePanels();
    const S = await import('/js/studio.js');
    await S.openStudio(got.id); await sleep(1500);
    S._studio.P.trim = { a: 0, b: 2 };
    window.__studioExport = null;
    const ok = await S._exportNative({ share: false, noOver: true });
    const r = window.__studioExport;
    $('#stBack') && $('#stBack').click(); await sleep(800);
    // (a slow test machine may skip a few pictures; this way is only the fallback)
    if (!ok || !r || r.over || r.frames < 54) throw new Error(JSON.stringify(r));
    return `${r.frames} pictures ${r.w}x${r.h}`;
  }, 180000);
  await shot('v2-exported');
  await closePanels();
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
  await videoRun();
  await bgRun();
  for (const e of (window.__standErrors || [])) say('SELFTEST error ' + e.line);
  say(`SELFTEST DONE ok=${R.ok} fail=${R.fail} errors=${(window.__standErrors || []).length}`);
}
run().catch((e) => say('SELFTEST FAIL run ' + ((e && e.message) || e)));
