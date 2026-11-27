// The scale chooser for the notebook: pick the key note, the scale, the instrument (which sets the
// clef and where the scale starts), the clef, how many octaves and which way, and see it engraved
// as you go. "Add to page" puts it on the page as printed music; tapping it later brings it back here.
import { SCALE_TYPES } from './scales.js';
import { tr, LANG } from './i18n.js';
import { INSTRUMENTS, scaleMusic, scaleKey, bestOctave, drawMusic, engrave } from './engrave.js';

// ---------- note names, spelled (F sharp, not G flat), as musicians of the language say them ----------
const SOLF = { pt: ['Dó', 'Ré', 'Mi', 'Fá', 'Sol', 'Lá', 'Si'], es: ['Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si'], it: ['Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si'], fr: ['Do', 'Ré', 'Mi', 'Fa', 'Sol', 'La', 'Si'] };
const SIGN = { '-2': '𝄫', '-1': '♭', 0: '', 1: '♯', 2: '𝄪' };
export function noteName(L, a, lang = LANG) {
  const b = String(lang).split('-')[0];
  if (SOLF[b]) return SOLF[b][L] + SIGN[a];
  if (b === 'de' || b === 'pl' || b === 'nl') {
    // (German letters: H is B natural and B is B flat; -is sharp, -es flat; the Dutch keep B and say Bes)
    const de = b !== 'nl', base = 'CDEFGA'[L] || (de ? 'H' : 'B');
    if (a === 0) return base;
    if (a > 0) return base + (a === 2 ? 'isis' : 'is');
    if (L === 6) return de ? (a === -1 ? 'B' : 'Heses') : (a === -1 ? 'Bes' : 'Beses');
    // (Es and As, not Ees and Aes; doubled: Eses, Asas)
    if (L === 2) return a === -1 ? 'Es' : 'Eses';
    if (L === 5) return a === -1 ? 'As' : 'Asas';
    return base + (a === -1 ? 'es' : 'eses');
  }
  return 'CDEFGAB'[L] + SIGN[a];
}
// "F♯ major", "Ré menor harmónica", "Fis · Dur"
export function scaleTitle(sc, lang = LANG) {
  const t = lang === 'en' ? (x) => x : tr;
  const kind = t((SCALE_TYPES[sc.type] || SCALE_TYPES.major).label), b = String(lang).split('-')[0];
  const name = noteName(sc.L, sc.a, lang);
  return ['en', 'pt', 'es', 'fr', 'it'].includes(b) ? name + ' ' + kind.charAt(0).toLowerCase() + kind.slice(1) : name + ' · ' + kind;
}
// the music of a scale for the page (lang 'en' for the layouts, which are written in English)
export function scaleItemMusic(sc, lang = LANG) {
  return scaleMusic(sc, { nameOf: (L, a) => noteName(L, a, lang), title: sc.title === false ? '' : scaleTitle(sc, lang) });
}

const DEF = { L: 0, a: 0, type: 'major', inst: 'cello', clef: 'bass', octaves: 2, dir: 'updown', ks: true, names: false, title: true, o: null };
const remembered = () => { try { return JSON.parse(localStorage.getItem('standScaleDlg') || 'null'); } catch { return null; } };
const instOf = (k) => INSTRUMENTS.find((i) => i.k === k) || INSTRUMENTS[INSTRUMENTS.length - 1];
// where the scale starts when nothing says otherwise: inside the instrument's range, fewest ledger lines
export function autoOctave(sc) {
  const I = instOf(sc.inst);
  return bestOctave({ L: sc.L, a: sc.a, type: sc.type, octaves: sc.octaves, clef: sc.clef, lo: I.lo, hi: I.hi, second: sc.clef !== I.clef });
}

const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
function seg(items, on, pick, cls = '') {
  const s = el('div', 'seg full ' + cls);
  for (const [v, label, aria, glyph] of items) {
    const b = el('button'); b.type = 'button'; b.dataset.v = v;
    if (glyph) { const g = el('span', 'sd-glyph', glyph); g.setAttribute('aria-hidden', 'true'); g.setAttribute('translate', 'no'); b.append(g); }
    if (label) b.append(el('span', '', label));
    if (aria) b.setAttribute('aria-label', aria);
    b.classList.toggle('on', String(v) === String(on));
    b.addEventListener('click', () => { pick(v); s.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); });
    s.append(b);
  }
  return s;
}
const field = (label, ctl, wide) => { const f = el('label', 'field' + (wide ? ' wide' : '')); f.append(el('span', '', label), ctl); return f; };

// open the chooser; resolves with the scale chosen, or null
export function openScaleDialog(start = null, { editing = false } = {}) {
  return new Promise((resolve) => {
    const sc = { ...DEF, ...(remembered() || {}), ...(start || {}) };
    if (!instOf(sc.inst).clefs.includes(sc.clef)) sc.clef = instOf(sc.inst).clef;
    if (sc.o == null) sc.o = autoOctave(sc);
    const back = el('div', 'ask-back');
    const box = el('div', 'ask scale-dlg'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Scale on a staff');
    box.append(el('p', 'ask-title', 'Scale on a staff'));
    // the music as it will look on the page
    const paper = el('div', 'sd-paper'), cv = el('canvas'); paper.append(cv);
    const note = el('p', 'hint sd-note'); note.hidden = true;
    box.append(paper, note);
    const body = el('div', 'sd-body');
    // the key note: a letter, then flat, natural or sharp
    const keyRow = el('div', 'sd-key');
    // (the names the player says: C D E…, Dó Ré Mi…, or C… H)
    const letters = seg([0, 1, 2, 3, 4, 5, 6].map((i) => [i, noteName(i, 0)]), sc.L, (v) => { sc.L = +v; reOct(); }, 'sd-letters');
    letters.setAttribute('translate', 'no');
    const accs = seg([[-1, '', 'Flat', '♭'], [0, '', 'Natural', '♮'], [1, '', 'Sharp', '♯']], sc.a, (v) => { sc.a = +v; reOct(); }, 'sd-accs');
    keyRow.append(letters, accs);
    body.append(field('Key note', keyRow, true));
    // the scale and the instrument
    const grid = el('div', 'field-grid');
    const type = el('select');
    for (const [k, d] of Object.entries(SCALE_TYPES)) { const o = el('option', '', d.label); o.value = k; type.append(o); }
    type.value = sc.type; type.addEventListener('change', () => { sc.type = type.value; reOct(); });
    const inst = el('select');
    for (const I of INSTRUMENTS) { const o = el('option', '', I.label); o.value = I.k; inst.append(o); }
    inst.value = sc.inst;
    inst.addEventListener('change', () => { sc.inst = inst.value; sc.clef = instOf(sc.inst).clef; buildClefs(); reOct(); });
    grid.append(field('Scale', type), field('Instrument', inst));
    body.append(grid);
    // the clef: the ones the instrument reads
    const clefBox = el('div');
    const CLEF_GLYPH = { treble: '\uE050', bass: '\uE062', alto: '\uE05C', tenor: '\uE05C', treble8: '\uE052' };
    const CLEF_NAME = { treble: 'Treble clef', bass: 'Bass clef', alto: 'Alto clef', tenor: 'Tenor clef', treble8: 'Treble 8vb' };
    function buildClefs() {
      clefBox.textContent = '';
      clefBox.append(seg(instOf(sc.inst).clefs.map((c) => [c, CLEF_NAME[c], null, CLEF_GLYPH[c]]), sc.clef, (v) => { sc.clef = v; reOct(); }, 'sd-clefs'));
    }
    buildClefs();
    body.append(field('Clef', clefBox, true));
    // octaves, direction, and where it starts
    const g2 = el('div', 'field-grid');
    g2.append(field('Octaves', seg([[1, '1'], [2, '2'], [3, '3'], [4, '4']], sc.octaves, (v) => { sc.octaves = +v; reOct(); })));
    const dir = el('select');
    for (const [v, t] of [['updown', 'Up and down'], ['up', 'Up'], ['down', 'Down']]) { const o = el('option', '', t); o.value = v; dir.append(o); }
    dir.value = sc.dir; dir.addEventListener('change', () => { sc.dir = dir.value; draw(); });
    g2.append(field('Direction', dir));
    body.append(g2);
    const startRow = el('div', 'sd-start');
    const lower = el('button', 'btn small', 'Lower'), higher = el('button', 'btn small', 'Higher'), from = el('b', 'num');
    from.setAttribute('translate', 'no');
    lower.type = higher.type = 'button';
    lower.addEventListener('click', () => { if (sc.o > 0) { sc.o--; draw(); } });
    higher.addEventListener('click', () => { if (sc.o < 7) { sc.o++; draw(); } });
    startRow.append(lower, from, higher);
    body.append(field('Starts on', startRow, true));
    // what is written with it
    const checks = el('div', 'sd-checks');
    const check = (label, k) => { const l = el('label', 'sd-check'); const c = el('input'); c.type = 'checkbox'; c.checked = sc[k] !== false; c.addEventListener('change', () => { sc[k] = c.checked; draw(); }); l.append(c, el('span', '', label)); return l; };
    checks.append(check('Key signature', 'ks'), check('Note names under the notes', 'names'), check('Name above the staff', 'title'));
    body.append(checks);
    box.append(body);
    const row = el('div', 'ask-row');
    const no = el('button', 'btn', 'Cancel'), yes = el('button', 'btn primary', editing ? 'Done' : 'Add to page');
    row.append(no, yes); box.append(row); back.append(box); document.body.append(back);
    const done = (v) => { back.remove(); resolve(v); };
    no.addEventListener('click', () => done(null));
    yes.addEventListener('click', () => { const out = { ...sc }; try { const { o, ...keep } = out; localStorage.setItem('standScaleDlg', JSON.stringify(keep)); } catch {} done(out); });
    back.addEventListener('click', (e) => { if (e.target === back) done(null); });
    // (a new key, scale, clef or number of octaves: start it where it reads best again)
    function reOct() { sc.o = autoOctave(sc); draw(); }
    function draw() {
      from.textContent = noteName(sc.L, sc.a) + sc.o;
      lower.disabled = sc.o <= 0; higher.disabled = sc.o >= 7;
      const m = scaleItemMusic(sc);
      const noKey = sc.ks !== false && scaleKey(sc.L, sc.a, sc.type) == null;
      note.hidden = !noKey;
      note.textContent = tr(['dim7', 'wholetone', 'chromatic'].includes(sc.type) ? 'This scale is written without a key signature: the sharps and flats are by the notes.' : 'This key has more than seven sharps or flats, so they are written by the notes.');
      const L = engrave(m), dpr = Math.min(3, window.devicePixelRatio || 1);
      const W = paper.clientWidth - 24 || 520, H = Math.round(W * (L.hs / L.ws));
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.width = W + 'px'; cv.style.height = H + 'px';
      const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      g.translate(W / 2, H / 2); drawMusic(g, m, W, H, '#1d1d1f');
      cv.setAttribute('aria-label', scaleTitle(sc) + ', ' + noteName(sc.L, sc.a) + sc.o);
    }
    const go = () => { draw(); setTimeout(() => yes.focus(), 30); };
    (document.fonts ? document.fonts.load('40px Bravura').catch(() => {}) : Promise.resolve()).then(() => requestAnimationFrame(go));
  });
}
