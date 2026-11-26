// The Mutopia Project's free scores (public domain or free licences), searched here on the iPad: a
// small list of every piece that comes as one PDF — its title, composer, opus, instruments and where
// its A4 PDF is — made from Mutopia's own sources. A score found here opens at once: no terms to
// accept, no waiting. Before one is shown, Stand asks Mutopia whether that PDF is really there.
import { fold } from './imslp.js';

const BASE = 'https://www.mutopiaproject.org/ftp/';
let list = null;
export async function mutopiaList() {
  if (!list) list = fetch(new URL('./mutopia.json', import.meta.url)).then((r) => r.json()).then((a) => a.map((e) => ({ ...e, f: fold([e.t, e.cn, e.c, e.o, e.i].join(' ')) })));
  return list;
}
export const mutopiaUrl = (e) => BASE + e.p;
// (words that say little: every piece has them)
const STOP = new Set(['the', 'a', 'an', 'in', 'for', 'of', 'and', 'de', 'la', 'le', 'des', 'du', 'et', 'en', 'per', 'fur', 'und', 'major', 'minor', 'dur', 'moll', 'no', 'nr', 'op', 'opus']);
// The pieces that have every word asked for (a word may be the start of one: "suit" finds "suite"),
// the best first: words in the title count most, the composer's name next.
export async function searchMutopia(q, max = 8) {
  const words = fold(q).split(/\s+/).filter((w) => w && !STOP.has(w));
  if (!words.length) return [];
  const all = await mutopiaList();
  const hits = [];
  for (const e of all) {
    const toks = e.f.split(' ');
    let ok = true, sc = 0;
    for (const w of words) {
      const exact = toks.includes(w), pre = exact || (w.length >= 3 && toks.some((t) => t.startsWith(w)));
      if (!pre) { ok = false; break; }
      const ti = fold(e.t).split(' '), inTitle = ti.includes(w) || ti.some((t) => t.startsWith(w));
      sc += (exact ? 2 : 1) + (inTitle ? 1.5 : 0);
    }
    if (ok) hits.push({ e, sc: sc - e.t.length * 0.005 });
  }
  hits.sort((a, b) => b.sc - a.sc);
  return hits.slice(0, max).map((h) => h.e);
}
