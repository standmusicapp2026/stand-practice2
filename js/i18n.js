// Stand in the language of the iPad, or the one chosen in Settings.
// The app is written in English; each other language is a list of the English words and their
// translation (js/lang/<lang>.json). What is on screen is translated as it appears: the page as it is
// loaded and everything put on it later (panels, hints, buttons made on the fly), word for word
// where it is the same, by pattern where it holds numbers or names ("{0} bars on this page").
// What people write themselves (titles, notes, names) is never touched: those places say
// translate="no".

export const LANGS = [
  ['en', 'English'], ['pt-PT', 'Português (Portugal)'], ['pt-BR', 'Português (Brasil)'], ['es', 'Español'],
  ['fr', 'Français'], ['de', 'Deutsch'], ['it', 'Italiano'], ['nl', 'Nederlands'], ['pl', 'Polski'],
  ['ru', 'Русский'], ['ja', '日本語'], ['zh-Hans', '简体中文'], ['ko', '한국어'],
];
const CODES = LANGS.map((l) => l[0]);

// the language asked for (Settings), else the first of the iPad's languages Stand has
function fit(tag) {
  if (!tag) return null;
  const t = String(tag).replace('_', '-'), low = t.toLowerCase(), base = low.split('-')[0];
  if (base === 'pt') return /-br\b/.test(low) ? 'pt-BR' : 'pt-PT';
  if (base === 'zh') return 'zh-Hans';
  if (base === 'nb' || base === 'no') return null;
  const hit = CODES.find((c) => c.toLowerCase() === low) || CODES.find((c) => c.toLowerCase() === base);
  return hit || null;
}
export function chosenLang() { try { return localStorage.getItem('standLang') || 'auto'; } catch { return 'auto'; } }
export function setChosenLang(v) { try { localStorage.setItem('standLang', v || 'auto'); } catch {} }
function pickLang() {
  try { if (globalThis.__lang) return fit(globalThis.__lang) || 'en'; } catch {}
  const c = chosenLang();
  if (c && c !== 'auto') { const f = fit(c); if (f) return f; }
  const list = (typeof navigator !== 'undefined' && (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language])) || [];
  for (const l of list) { const f = fit(l); if (f) return f; }
  return 'en';
}
export const LANG = pickLang();
try { if (typeof document !== 'undefined') document.documentElement.lang = LANG; } catch {}

let DICT = null;           // English -> translation
let PATS = [];             // [regex, translation with {0}…] for the words with numbers or names in them
const BYWORD = new Map();  // a word -> the patterns that have it (a text is tried only against those)
const NONE = new Set();    // texts with no translation (not tried again)
const KEEP = new WeakSet(); // text nodes already in the language (never translated twice)

export async function loadLang() {
  if (LANG === 'en') return;
  try {
    const r = await fetch('js/lang/' + LANG + '.json', { cache: 'no-cache' });
    if (!r.ok) return;
    const d = await r.json();
    DICT = new Map();
    PATS = [];
    for (const [k, v] of Object.entries(d)) {
      if (!v || k.startsWith('//')) continue;
      if (/\{\d\}/.test(k)) {
        // "{0} bars on this page" — the parts in braces stand for anything (numbers, names)
        const parts = k.split(/(\{\d\})/);
        const order = [];
        const re = parts.map((p) => { const m = p.match(/^\{(\d)\}$/); if (m) { order.push(+m[1]); return '(.+?)'; } return p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('');
        const words = k.replace(/\{\d\}/g, ' ').toLowerCase().match(/\p{L}{3,}/gu) || [];
        const anchor = words.sort((x, y) => y.length - x.length)[0] || '';
        PATS.push([new RegExp('^' + re + '$', 's'), v, order, k.replace(/\{\d\}/g, '').length, anchor]);
      } else DICT.set(k, v);
    }
    // (the longest fixed words first: the most exact pattern wins; each found by its longest word)
    PATS.sort((a, b) => b[3] - a[3]);
    for (const P of PATS) { const k = P[4]; if (!BYWORD.has(k)) BYWORD.set(k, []); BYWORD.get(k).push(P); }
  } catch (err) { console.warn('language', err); }
}

// One piece of English in the language (or as it is, when it has no translation).
export function tr(s) {
  if (!DICT || s == null) return s;
  const str = String(s);
  const t = str.trim(); if (!t) return s;
  let v = DICT.get(t);
  // (two or more sentences put together: each one in turn, when Stand knows them all)
  if (v == null && !NONE.has(t) && /[.!?…]\s+\S/.test(t)) {
    const parts = t.split(/(?<=[.!?…])\s+(?=[\p{Lu}0-9«“"(])/u);
    if (parts.length > 1 && parts.length < 12) {
      // (cut it into runs of sentences that Stand knows: the longest known run first)
      const one = (x) => { const d = DICT.get(x); if (d != null) return d; const y = tr(x); return y !== x ? y : null; };
      const outs = []; let i = 0;
      while (i < parts.length) {
        let got = null, j = parts.length;
        for (; j > i; j--) { const run = parts.slice(i, j).join(' '); got = j - i > 1 ? DICT.get(run) : one(run); if (got != null) break; }
        if (got == null) { outs.length = 0; break; }
        outs.push(got); i = j;
      }
      if (outs.length && i >= parts.length) v = outs.join(' ');
    }
  }
  if (v == null && !NONE.has(t)) {
    const cands = new Set(); const ws = t.toLowerCase().match(/\p{L}{3,}/gu) || [];
    for (const w of ws) { const l = BYWORD.get(w); if (l) for (const P of l) cands.add(P); }
    const l0 = BYWORD.get(''); if (l0) for (const P of l0) cands.add(P);
    for (const [re, out, order] of [...cands].sort((a, b) => b[3] - a[3])) {
      const m = t.match(re);
      // (what fills the braces is a name, a number or a few words: never a sentence of its own)
      if (m && m.slice(1).some((x) => x && (x.length > 60 || /[.!?]\s+[\p{Lu}0-9]/u.test(x)))) continue;
      if (m) {
        // (what stands in the braces is itself translated when it is a word Stand knows: "Violin")
        const vals = {}; order.forEach((n, i) => { const x = m[i + 1]; vals[n] = DICT.get(x) ?? (x && x.length > 3 && x.length < t.length && /\p{L}/u.test(x) ? tr(x) : x); });
        v = out.replace(/\{(\d)\}/g, (_, n) => (vals[n] != null ? vals[n] : ''));
        break;
      }
    }
  }
  if (v == null) { if (NONE.size > 5000) NONE.clear(); NONE.add(t); return s; }
  return t === str ? v : str.replace(t, v);
}
export const translating = () => !!DICT;

// ---------- what is on screen ----------
const ATTRS = ['aria-label', 'placeholder', 'title', 'data-tip', 'data-label', 'label'];
// (and the names people gave their things: score and folder titles, the score's title on top)
const SKIP = 'script,style,textarea,code,[translate="no"],[contenteditable="true"],[contenteditable=""],.ttl,#scoreTitle';
function skipped(el) { return !el || (el.closest && el.closest(SKIP)); }
function doText(n) {
  if (KEEP.has(n)) return;
  const p = n.parentElement; if (skipped(p)) return;
  const v = n.nodeValue; if (!v || !/[A-Za-z]/.test(v)) return;
  // (a word that means something else in one place: "Bass" as a clef, not the voice — data-tr-ctx)
  const cx = p.closest('[data-tr-ctx]');
  const inCtx = cx && DICT.get(cx.dataset.trCtx + '|' + v.trim());
  const out = inCtx != null ? v.replace(v.trim(), inCtx) : tr(v);
  if (out !== v) {
    KEEP.add(n); n.nodeValue = out;
    // (the English kept beside it, for the few places that look at what a label says)
    if (p.childNodes.length === 1) p.dataset.en = v.trim();
  }
}
function doAttrs(el) {
  // (a text field's hint is the app's, even though what is typed in it is the person's)
  if (!el || !el.closest || el.closest('script,style,code,[translate="no"],.ttl,#scoreTitle')) return;
  const cx = el.closest('[data-tr-ctx]');
  for (const a of ATTRS) {
    const v = el.getAttribute && el.getAttribute(a);
    if (!v || !/[A-Za-z]/.test(v)) continue;
    const inCtx = cx && DICT.get(cx.dataset.trCtx + '|' + v.trim());
    const out = inCtx != null ? inCtx : tr(v); if (out !== v) el.setAttribute(a, out);
  }
  // buttons that are inputs ("Done"), and option labels
  if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit') && el.value) { const out = tr(el.value); if (out !== el.value) el.value = out; }
}
function walk(root) {
  if (!root) return;
  if (root.nodeType === 3) { doText(root); return; }
  if (root.nodeType !== 1) return;
  if (skipped(root)) { if (root.matches && root.matches('textarea,[contenteditable]')) doAttrs(root); return; }
  doAttrs(root);
  const it = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => { if (n.nodeType === 1 && n.matches && n.matches(SKIP)) { if (n.matches('textarea,[contenteditable]')) doAttrs(n); return NodeFilter.FILTER_REJECT; } return NodeFilter.FILTER_ACCEPT; },
  });
  let n; while ((n = it.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
}
export function translatePage() {
  if (!DICT || typeof document === 'undefined') return;
  walk(document.body);
  document.title = tr(document.title);
  const mo = new MutationObserver((list) => {
    for (const m of list) {
      if (m.type === 'childList') { for (const n of m.addedNodes) walk(n); }
      else if (m.type === 'characterData') { KEEP.delete(m.target); doText(m.target); }
      else if (m.type === 'attributes' && ATTRS.includes(m.attributeName)) doAttrs(m.target);
    }
  });
  mo.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}

// ---------- note names as musicians of the language say them ----------
// (do-re-mi where they sing it; the German letters — H for B, B for B flat — where they use them)
const NAMES = {
  latin: ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B'],
  pt: ['Dó', 'Dó♯', 'Ré', 'Mi♭', 'Mi', 'Fá', 'Fá♯', 'Sol', 'Lá♭', 'Lá', 'Si♭', 'Si'],
  es: ['Do', 'Do♯', 'Re', 'Mi♭', 'Mi', 'Fa', 'Fa♯', 'Sol', 'La♭', 'La', 'Si♭', 'Si'],
  fr: ['Do', 'Do♯', 'Ré', 'Mi♭', 'Mi', 'Fa', 'Fa♯', 'Sol', 'La♭', 'La', 'Si♭', 'Si'],
  it: ['Do', 'Do♯', 'Re', 'Mi♭', 'Mi', 'Fa', 'Fa♯', 'Sol', 'La♭', 'La', 'Si♭', 'Si'],
  de: ['C', 'Cis', 'D', 'Es', 'E', 'F', 'Fis', 'G', 'As', 'A', 'B', 'H'],
  pl: ['C', 'Cis', 'D', 'Es', 'E', 'F', 'Fis', 'G', 'As', 'A', 'B', 'H'],
  nl: ['C', 'Cis', 'D', 'Es', 'E', 'F', 'Fis', 'G', 'As', 'A', 'Bes', 'B'],
};
export function noteNames(lang = LANG) {
  const b = String(lang).split('-')[0];
  return (NAMES[b] || NAMES.latin).slice();
}
