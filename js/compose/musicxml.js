// MusicXML 4.0 export (.musicxml and compressed .mxl) and import, so scores move to and from
// Sibelius, Dorico, MuseScore and Finale.
import { INST, INSTRUMENTS } from './instruments.js';
import { hasVoice2, hasVoice, voiceView,
  WHOLE, STEP_NAMES, barTicks, evTicks, timeAt, keyAt, ticksOf, toWritten, writtenKey, clefAt, clefEnd, newId, newScore, restBar, tidyBar, restsFor, valueOf, midiOf, newPart, spansToMarks, migrateScore, fifthsOfInterval, lyricOf, versesOf, setLyric, MAX_VERSES,
} from './model.js';
import * as M0 from './model.js';
import { beamPlan } from './engrave.js';

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const TYPE = { 1: 'whole', 2: 'half', 4: 'quarter', 8: 'eighth', 16: '16th', 32: '32nd', 64: '64th', 128: '128th' };
const TYPE_BACK = Object.fromEntries(Object.entries(TYPE).map(([k, v]) => [v, +k]));
const CLEF_XML = { treble: ['G', 2, 0], bass: ['F', 4, 0], alto: ['C', 3, 0], tenor: ['C', 4, 0], treble8: ['G', 2, -1], bass8: ['F', 4, -1], perc: ['percussion', 0, 0], treble8va: ['G', 2, 1], bass8va: ['F', 4, 1], soprano: ['C', 1, 0], mezzo: ['C', 2, 0], baritoneC: ['C', 5, 0], baritoneF: ['F', 3, 0], frenchviolin: ['G', 1, 0] };
const ART_XML = { stacc: 'staccato', stacciss: 'staccatissimo', ten: 'tenuto', acc: 'accent', marc: 'strong-accent', breath: 'breath-mark', caes: 'caesura' };
const ORN_XML = { trill: 'trill-mark', mord: 'mordent', prall: 'inverted-mordent', turn: 'turn', turnInv: 'inverted-turn' };
const OTT = { '8va': 1, '8vb': 1, '15ma': 1, '15mb': 1 };
const JUMP_WORDS = { dc: 'D.C.', dcfine: 'D.C. al Fine', dccoda: 'D.C. al Coda', ds: 'D.S.', dsfine: 'D.S. al Fine', dscoda: 'D.S. al Coda', tocoda: 'To Coda', fine: 'Fine' };
const GM = { piano: 1, harpsichord: 7, celesta: 9, glockenspiel: 10, vibraphone: 12, marimba: 13, xylophone: 14, bells: 15, organ: 20, accordion: 22, guitar: 25, steelguitar: 26, eguitar: 28, jazzbass: 33, ebass: 34, violin: 41, viola: 42, cello: 43, bass: 44, violins: 49, violas: 49, cellos: 49, basses: 49, tremolo: 45, pizz: 46, harp: 47, timpani: 48, strings: 49, choir: 53, oohs: 54, trumpet: 57, trombone: 58, tuba: 59, horn: 61, brass: 62, sopsax: 65, altosax: 66, tenorsax: 67, barisax: 68, oboe: 69, englishhorn: 70, bassoon: 71, clarinet: 72, piccolo: 73, flute: 74, recorder: 75, banjo: 106, woodblock: 116, drum: 119, snare: 119, bassdrum: 119, toms: 119, cymbals: 120, suspcymbal: 120, tambourine: 119, bongos: 119, triangle: 114,  epiano: 5 };

export function toMusicXML(score0) {
  const score = spansToMarks(score0);
  const out = [];
  const w = (s) => out.push(s);
  w('<?xml version="1.0" encoding="UTF-8" standalone="no"?>');
  w('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">');
  w('<score-partwise version="4.0">');
  w(`<work><work-title>${esc(score.title)}</work-title></work>`);
  if (score.subtitle) w(`<movement-title>${esc(score.subtitle)}</movement-title>`);
  w('<identification>');
  if (score.composer) w(`<creator type="composer">${esc(score.composer)}</creator>`);
  if (score.lyricist) w(`<creator type="lyricist">${esc(score.lyricist)}</creator>`);
  if (score.arranger) w(`<creator type="arranger">${esc(score.arranger)}</creator>`);
  if (score.rights) w(`<rights>${esc(score.rights)}</rights>`);
  w(`<encoding><software>Stand</software><encoding-date>${new Date().toISOString().slice(0, 10)}</encoding-date></encoding></identification>`);
  w('<part-list>');
  score.parts.forEach((p, i) => {
    const inst = M0.instOf(p), id = 'P' + (i + 1);
    w(`<score-part id="${id}"><part-name>${esc(p.name)}</part-name><part-abbreviation>${esc(p.abbr)}</part-abbreviation>`);
    w(`<score-instrument id="${id}-I1"><instrument-name>${esc(inst.name)}</instrument-name></score-instrument>`);
    w(`<midi-instrument id="${id}-I1"><midi-channel>${(i % 15) + 1 + (i % 15 >= 9 ? 1 : 0)}</midi-channel><midi-program>${GM[p.sound || inst.sound] || 1}</midi-program></midi-instrument></score-part>`);
  });
  w('</part-list>');
  score.parts.forEach((p, pi) => {
    const inst0 = M0.instOf(p);
    w(`<part id="P${pi + 1}">`);
    for (let m = 0; m < score.measures.length; m++) {
      const ms = score.measures[m];
      // (the instrument in this bar: a part may change instrument; from there on its own transposition)
      const inst = p.instCh ? M0.instAt(p, m) : inst0, chHere = !!(p.instCh && m > 0 && p.instCh[m] !== undefined);
      const prevI = chHere ? M0.instAt(p, m - 1) : inst;
      const trDiff = chHere && ((prevI.tr || {}).steps !== (inst.tr || {}).steps || (prevI.tr || {}).semis !== (inst.tr || {}).semis);
      const time = timeAt(score, m);
      const short = (m === 0 && M0.pickupOf(score)) || (ms.len > 0 && ms.len < (time[0] * WHOLE) / time[1]);
      w(`<measure number="${M0.barNumber(score, m)}"${short ? ' implicit="yes"' : ''}>`);
      if (ms.start === 'repeat') w('<barline location="left"><bar-style>heavy-light</bar-style><repeat direction="forward"/></barline>');
      // attributes: at the start and where things change
      const attrs = [];
      if (m === 0) attrs.push(`<divisions>${WHOLE / 4}</divisions>`);
      if (m === 0 || (ms.key !== undefined && ms.key !== null) || (trDiff && writtenKey(keyAt(score, m), prevI) !== writtenKey(keyAt(score, m), inst))) attrs.push(`<key><fifths>${writtenKey(keyAt(score, m), inst)}</fifths></key>`);
      if (m === 0 || ms.time) attrs.push(`<time${ms.timeSym ? ` symbol="${ms.timeSym}"` : ''}${ms.timeHide ? ' print-object="no"' : ''}><beats>${time[0]}</beats><beat-type>${time[1]}</beat-type></time>`);
      if (m === 0 && p.staves.length > 1) attrs.push(`<staves>${p.staves.length}</staves>`);
      p.staves.forEach((st, si) => {
        const clef = clefAt(st, m);
        if (m === 0 || (st.clefs && st.clefs[m] && clef !== clefEnd(st, m - 1))) {
          const [sign, line, oct] = CLEF_XML[clef] || CLEF_XML.treble;
          attrs.push(`<clef${p.staves.length > 1 ? ` number="${si + 1}"` : ''}><sign>${sign}</sign>${line ? `<line>${line}</line>` : ''}${oct ? `<clef-octave-change>${oct}</clef-octave-change>` : ''}</clef>`);
        }
      });
      if (m === 0) p.staves.forEach((st, si) => { const nl = st.lines || inst.lines || 5; if (nl !== 5) attrs.push(`<staff-details${p.staves.length > 1 ? ` number="${si + 1}"` : ''}><staff-lines>${nl}</staff-lines></staff-details>`); });
      if (trDiff) attrs.push(`<transpose><diatonic>${(inst.tr || {}).steps || 0}</diatonic><chromatic>${(inst.tr || {}).semis || 0}</chromatic></transpose>`);
      if (m === 0 && inst.tr && (inst.tr.semis || inst.tr.steps)) attrs.push(`<transpose><diatonic>${inst.tr.steps}</diatonic><chromatic>${inst.tr.semis}</chromatic></transpose>`);
      if (attrs.length) w(`<attributes>${attrs.join('')}</attributes>`);
      if (chHere) w(`<direction placement="above"><direction-type><words font-style="italic">${esc(p.instCh[m] ? inst.name : p.name)}</words></direction-type><sound><midi-instrument id="P${pi + 1}-I1"><midi-program>${GM[inst.sound] || 1}</midi-program></midi-instrument></sound></direction>`);
      if (ms.tempo && pi === 0) {
        const unit = ms.tempo.beat === 2 ? 'half' : ms.tempo.beat === 8 ? 'eighth' : 'quarter';
        w(`<direction placement="above"><direction-type>${ms.tempo.text ? `<words font-weight="bold">${esc(ms.tempo.text)}</words></direction-type><direction-type>` : ''}<metronome><beat-unit>${unit}</beat-unit>${ms.tempo.dotted ? '<beat-unit-dot/>' : ''}<per-minute>${ms.tempo.bpm}</per-minute></metronome></direction-type><sound tempo="${Math.round(ms.tempo.bpm * (4 / (ms.tempo.beat || 4)) * (ms.tempo.dotted ? 1.5 : 1))}"/></direction>`);
      }
      if (ms.rehearsal && pi === 0) w(`<direction placement="above"><direction-type><rehearsal>${esc(ms.rehearsal)}</rehearsal></direction-type></direction>`);
      if (ms.mark && pi === 0) w(`<direction placement="above"><direction-type><${ms.mark}/></direction-type><sound ${ms.mark}="${ms.mark}${m}"/></direction>`);
      const volta = (score.spans || []).find((q) => q.kind === 'volta' && q.a.m <= m && q.b.m >= m);
      if (volta && volta.a.m === m) w(`<barline location="left"><ending number="${volta.n || 1}" type="start">${volta.n || 1}.</ending></barline>`);
      p.staves.forEach((st, si) => {
        if (si > 0) w(`<backup><duration>${barTicks(time)}</duration></backup>`);
        const staffTag = p.staves.length > 1 ? `<staff>${si + 1}</staff>` : '';
        const lyrState = { hyph: false };
        for (const [voice, bar] of [[si * 4 + 1, st.bars[m] || restBar(time)], ...[2, 3, 4].filter((v) => hasVoice(st, v, m)).map((v) => [si * 4 + v, st['v' + v][m]])]) {
        if (voice % 4 !== 1) w(`<backup><duration>${barTicks(time)}</duration></backup>`);
        // where each tuplet group starts and stops (for the bracket and number)
        TUPM = new Map();
        for (let i = 0; i < bar.length;) {
          const e0 = bar[i]; if (!e0.tup) { i++; continue; }
          const target = e0.tup.m * (1920 / (e0.tup.base || e0.t)); let acc = 0, j = i;
          while (j < bar.length && bar[j].tup && bar[j].tup.n === e0.tup.n) { acc += ticksOf(bar[j], time); j++; if (acc >= target - 1) break; }
          TUPM.set(bar[i], 'start'); if (j - 1 > i) TUPM.set(bar[j - 1], 'stop'); i = j;
        }
        // (the beams as drawn, so other programs show the same: also those set by hand)
        const BEAMM = beamPlan(bar, time);
        for (const ev of bar) {
          const dur = ticksOf(ev, time);
          if (ev.dyn) w(`<direction placement="below"><direction-type><dynamics><${ev.dyn}/></dynamics></direction-type>${staffTag}</direction>`);
          if (ev.hp === '<' || ev.hp === '>') w(`<direction placement="below"><direction-type><wedge type="${ev.hp === '<' ? 'crescendo' : 'diminuendo'}"/></direction-type>${staffTag}</direction>`);
          if (ev.hp === 'end') w(`<direction placement="below"><direction-type><wedge type="stop"/></direction-type>${staffTag}</direction>`);
          if (ev.txt) w(`<direction placement="above"><direction-type><words${ev.txtStyle === 'tech' || ev.txtStyle === 'box' || ev.txtStyle === 'plain' ? '' : ' font-style="italic"'}${ev.txtStyle === 'box' ? ' enclosure="rectangle"' : ''}>${esc(ev.txt)}</words></direction-type>${staffTag}</direction>`);
          // lines that start or stop here
          let pos0 = 0; for (const q of bar) { if (q === ev) break; pos0 += ticksOf(q, time); }
          for (const sp of score.spans || []) {
            if (sp.st !== st.id) continue;
            const startsHere = sp.a.m === m && sp.a.pos >= pos0 && sp.a.pos < pos0 + dur, stopsHere = sp.b.m === m && sp.b.pos >= pos0 && sp.b.pos < pos0 + dur;
            const below = ['8vb', '15mb', 'ped', 'cresc', 'dim'].includes(sp.kind) ? 'below' : 'above';
            const n = (sp.id.length % 5) + 1;
            if (startsHere) {
              if (sp.kind === '8va' || sp.kind === '8vb' || sp.kind === '15ma' || sp.kind === '15mb') w(`<direction placement="${below}"><direction-type><octave-shift type="${sp.kind.includes('v') && sp.kind.endsWith('a') || sp.kind === '15ma' ? 'down' : 'up'}" size="${sp.kind.startsWith('15') ? 15 : 8}" number="${n}"/></direction-type>${staffTag}</direction>`);
              if (sp.kind === 'ped') w(`<direction placement="below"><direction-type><pedal type="start" line="${sp.line === false ? 'no' : 'yes'}"/></direction-type>${staffTag}</direction>`);
              if (['rit', 'accel', 'cresc', 'dim'].includes(sp.kind)) w(`<direction placement="${below}"><direction-type><words font-style="italic">${{ rit: 'rit.', accel: 'accel.', cresc: 'cresc.', dim: 'dim.' }[sp.kind]}</words></direction-type><direction-type><dashes type="start" number="${n}"/></direction-type>${staffTag}</direction>`);
            }
            if (stopsHere && !startsHere) {
              if (OTT[sp.kind]) w(`<direction placement="${below}"><direction-type><octave-shift type="stop" size="${sp.kind.startsWith('15') ? 15 : 8}" number="${n}"/></direction-type>${staffTag}</direction>`);
              if (sp.kind === 'ped') w(`<direction placement="below"><direction-type><pedal type="stop" line="${sp.line === false ? 'no' : 'yes'}"/></direction-type>${staffTag}</direction>`);
              if (['rit', 'accel', 'cresc', 'dim'].includes(sp.kind)) w(`<direction placement="${below}"><direction-type><dashes type="stop" number="${n}"/></direction-type>${staffTag}</direction>`);
            }
          }
          const common = (first) => {
            let s = `<duration>${dur}</duration>`;
            return s;
          };
          if (ev.rest || !ev.notes || !ev.notes.length) {
            w(`<note>${ev.cue ? '<cue/>' : ''}<rest${ev.full ? ' measure="yes"' : ''}/>${common(true)}<voice>${voice}</voice>${ev.full ? '' : `<type${ev.cue || ev.small ? ' size="cue"' : ''}>${TYPE[ev.t]}</type>${'<dot/>'.repeat(ev.dots || 0)}`}${tupXml(ev)}${headXml(ev.head)}${staffTag}${notations(ev, null, true)}</note>`);
            continue;
          }
          if (ev.chord) w(harmonyXml(ev.chord, staffTag));
          // a clef change in the middle of the bar, before this note
          if (ev.clef && voice % 4 === 1) { const [sign, line, oct] = CLEF_XML[ev.clef] || CLEF_XML.treble; w(`<attributes><clef${p.staves.length > 1 ? ` number="${si + 1}"` : ''}><sign>${sign}</sign>${line ? `<line>${line}</line>` : ''}${oct ? `<clef-octave-change>${oct}</clef-octave-change>` : ''}</clef></attributes>`); }
          if (ev.grace && !inst.unpitched) {
            const gs = [ev.grace, ...(ev.graceMore || [])];
            gs.forEach((g, gi) => {
              const gn = toWritten({ s: g.s, a: g.a || 0 }, inst);
              const sc = ((gn.s % 7) + 7) % 7, oct = Math.floor(gn.s / 7);
              const beam = gs.length > 1 ? `<beam number="1">${gi === 0 ? 'begin' : gi === gs.length - 1 ? 'end' : 'continue'}</beam><beam number="2">${gi === 0 ? 'begin' : gi === gs.length - 1 ? 'end' : 'continue'}</beam>` : '';
              w(`<note><grace${ev.grace.slash === false || (gs.length > 1 && gi > 0) ? '' : ' slash="yes"'}/><pitch><step>${STEP_NAMES[sc]}</step>${gn.a ? `<alter>${gn.a}</alter>` : ''}<octave>${oct}</octave></pitch><voice>${voice}</voice><type>${gs.length > 1 ? '16th' : 'eighth'}</type>${g.acc !== undefined && g.acc !== null ? `<accidental>${{ '-2': 'flat-flat', '-1': 'flat', 0: 'natural', 1: 'sharp', 2: 'double-sharp' }[gn.a || 0]}</accidental>` : ''}<stem>up</stem>${staffTag}${beam}</note>`);
            });
          }
          ev.notes.forEach((n0, k) => {
            const n = inst.unpitched ? n0 : toWritten(n0, inst);
            const sc = ((n.s % 7) + 7) % 7, oct = Math.floor(n.s / 7);
            const pitch = inst.unpitched ? `<unpitched><display-step>${STEP_NAMES[sc]}</display-step><display-octave>${oct}</display-octave></unpitched>` : `<pitch><step>${STEP_NAMES[sc]}</step>${n.a ? `<alter>${n.a}</alter>` : ''}<octave>${oct}</octave></pitch>`;
            const tieIn = isTiedFrom(voice % 4 !== 1 ? voiceView(st, ((voice - 1) % 4) + 1, score) : st, m, ev, n0);
            const ties = ev.cue ? '' : (tieIn ? '<tie type="stop"/>' : '') + (n0.tie ? '<tie type="start"/>' : '');
            w(`<note>${ev.cue ? '<cue/>' : ''}${k ? '<chord/>' : ''}${pitch}${common(!k)}${ties}<voice>${voice}</voice><type${ev.cue || ev.small ? ' size="cue"' : ''}>${TYPE[ev.t]}</type>${'<dot/>'.repeat(ev.dots || 0)}${n0.cau ? `<accidental parentheses="yes" cautionary="yes">${{ '-2': 'flat-flat', '-1': 'flat', 0: 'natural', 1: 'sharp', 2: 'double-sharp' }[n.a || 0]}</accidental>` : ''}${tupXml(ev)}${headXml(n0.head || ev.head)}${staffTag}${k === 0 && BEAMM.has(ev) ? BEAMM.get(ev).map((b, l) => `<beam number="${l + 1}">${b}</beam>`).join('') : ''}${notations(ev, n0, k === 0, tieIn, k === 0 ? lineMarks(score, st.id, m, pos0, dur) : '')}${k === 0 && (ev.lyric || ev.lyricV) ? lyricsXml(ev, lyrState) : ''}</note>`);
          });
        }
        }
      });
      if (ms.jump && pi === 0) w(`<direction placement="above"><direction-type><words font-style="italic">${JUMP_WORDS[ms.jump] || ''}</words></direction-type>${ms.jump === 'fine' ? '<sound fine="yes"/>' : ms.jump.startsWith('dc') ? '<sound dacapo="yes"/>' : ''}</direction>`);
      const bl = ms.bar;
      const vEnd = (score.spans || []).find((q) => q.kind === 'volta' && q.b.m === m);
      if (vEnd) w(`<barline location="right">${bl === 'repeat' ? '<bar-style>light-heavy</bar-style>' : ''}<ending number="${vEnd.n || 1}" type="${vEnd.closed === false ? 'discontinue' : 'stop'}"/>${bl === 'repeat' ? '<repeat direction="backward"/>' : ''}</barline>`);
      if (vEnd && bl === 'repeat') { /* written above with the ending */ }
      else if (bl === 'final') w('<barline location="right"><bar-style>light-heavy</bar-style></barline>');
      else if (bl === 'double') w('<barline location="right"><bar-style>light-light</bar-style></barline>');
      else if (bl === 'repeat') w('<barline location="right"><bar-style>light-heavy</bar-style><repeat direction="backward"/></barline>');
      w('</measure>');
    }
    w('</part>');
  });
  w('</score-partwise>');
  return out.join('\n');
}
const HEAD_XML = { x: 'x', diamond: 'diamond', slash: 'slash', tri: 'triangle', square: 'square', circlex: 'circle-x', ghost: 'normal" parentheses="yes', harm: 'diamond' };
const HEAD_BACK = { x: 'x', cross: 'x', diamond: 'diamond', slash: 'slash', triangle: 'tri', square: 'square', 'circle-x': 'circlex' };
function headXml(h) { return h && HEAD_XML[h] ? `<notehead>${HEAD_XML[h]}</notehead>`.replace('<notehead>normal" parentheses="yes</notehead>', '<notehead parentheses="yes">normal</notehead>') : ''; }
let TUPM = new Map();
const TUPC = {};
function tupXml(ev) { return ev.tup ? `<time-modification><actual-notes>${ev.tup.n}</actual-notes><normal-notes>${ev.tup.m}</normal-notes></time-modification>` : ''; }
function isTiedFrom(st, m, ev, n) {
  const bar = st.bars[m]; const i = bar.indexOf(ev);
  const prev = i > 0 ? bar[i - 1] : m > 0 ? st.bars[m - 1][st.bars[m - 1].length - 1] : null;
  return !!(prev && prev.notes && prev.notes.some((q) => q.tie && q.s === n.s));
}
function lyricXml(l, st, v = 1) {
  const cont = /-$/.test(l), text = l.replace(/-$/, '');
  const h = st.h || (st.h = {});
  const syl = h[v] ? (cont ? 'middle' : 'end') : (cont ? 'begin' : 'single');
  h[v] = cont;
  return `<lyric number="${v}"><syllabic>${syl}</syllabic><text>${esc(text)}</text></lyric>`;
}
// every verse of the note's lyrics
function lyricsXml(ev, st) { let x = ''; for (let v = 1, n = versesOf(ev); v <= n; v++) { const l = lyricOf(ev, v); if (l) x += lyricXml(l, st, v); } return x; }
const KINDS = [['maj7', 'major-seventh'], ['m7b5', 'half-diminished'], ['m7', 'minor-seventh'], ['dim7', 'diminished-seventh'], ['dim', 'diminished'], ['°', 'diminished'], ['aug', 'augmented'], ['+', 'augmented'], ['sus4', 'suspended-fourth'], ['sus2', 'suspended-second'], ['m6', 'minor-sixth'], ['m', 'minor'], ['13', 'dominant-13th'], ['11', 'dominant-11th'], ['9', 'dominant-ninth'], ['7', 'dominant'], ['6', 'major-sixth'], ['', 'major']];
function harmonyXml(c, staffTag) {
  const mm = /^([A-G])([#b]?)(.*?)(?:\/([A-G])([#b]?))?$/.exec(c.trim());
  if (!mm) return `<direction placement="above"><direction-type><words>${esc(c)}</words></direction-type>${staffTag}</direction>`;
  const alt = (x) => (x === '#' ? '<root-alter>1</root-alter>' : x === 'b' ? '<root-alter>-1</root-alter>' : '');
  const rest = mm[3] || ''; const kind = (KINDS.find(([k]) => rest.startsWith(k)) || ['', 'major'])[1];
  return `<harmony><root><root-step>${mm[1]}</root-step>${alt(mm[2])}</root><kind text="${esc(rest)}">${kind}</kind>${mm[4] ? `<bass><bass-step>${mm[4]}</bass-step>${mm[5] ? `<bass-alter>${mm[5] === '#' ? 1 : -1}</bass-alter>` : ''}</bass>` : ''}${staffTag}</harmony>`;
}
// trills with a wavy line and glissandos are written on their first and last notes
function lineMarks(score, stId, m, pos, dur) {
  let out = '';
  for (const sp of score.spans || []) {
    if (sp.st !== stId || (sp.kind !== 'trill' && sp.kind !== 'gliss')) continue;
    const at = (q) => q.m === m && q.pos >= pos && q.pos < pos + dur;
    if (sp.kind === 'trill') { if (at(sp.a)) out += '<ornaments><trill-mark/><wavy-line type="start"/></ornaments>'; if (at(sp.b)) out += '<ornaments><wavy-line type="stop"/></ornaments>'; }
    else { if (at(sp.a)) out += '<glissando type="start" line-type="solid">gliss.</glissando>'; if (at(sp.b) && !at(sp.a)) out += '<glissando type="stop"/>'; }
  }
  return out;
}
function notations(ev, n, first, tieIn, extra) {
  const parts = [];
  if (extra) parts.push(extra);
  if (n && n.tie) parts.push('<tied type="start"/>');
  if (n && tieIn) parts.push('<tied type="stop"/>');
  if (first) {
    if (ev.slur === 'start') parts.push('<slur type="start" number="1"/>');
    if (ev.slur === 'end') parts.push('<slur type="stop" number="1"/>');
    const arts = (ev.art || []).filter((a) => ART_XML[a]).map((a) => `<${ART_XML[a]}/>`);
    if (arts.length) parts.push(`<articulations>${arts.join('')}</articulations>`);
    if ((ev.art || []).includes('ferm')) parts.push('<fermata type="upright"/>');
    if ((ev.art || []).includes('fermS')) parts.push('<fermata type="upright">angled</fermata>');
    if ((ev.art || []).includes('fermL')) parts.push('<fermata type="upright">square</fermata>');
    if ((ev.art || []).includes('arp')) parts.push('<arpeggiate/>');
    const tech = [];
    if ((ev.art || []).includes('stopped')) tech.push('<stopped/>');
    if ((ev.art || []).includes('open')) tech.push('<open-string/>');
    if ((ev.art || []).includes('snap')) tech.push('<snap-pizzicato/>');
    if ((ev.art || []).includes('up')) tech.push('<up-bow/>');
    if ((ev.art || []).includes('down')) tech.push('<down-bow/>');
    if ((ev.art || []).includes('harm')) tech.push('<harmonic/>');
    if (ev.fing) for (const d of String(ev.fing).split(/[\s,]+/).filter(Boolean)) tech.push(`<fingering>${esc(d)}</fingering>`);
    if (ev.str) { const k = { I: 1, II: 2, III: 3, IV: 4 }[ev.str]; if (k) tech.push(`<string>${k}</string>`); }
    if (tech.length) parts.push(`<technical>${tech.join('')}</technical>`);
    const orn = (ev.art || []).filter((a) => ORN_XML[a]).map((a) => `<${ORN_XML[a]}/>`);
    const tr = (ev.art || []).find((a) => a === 'trem' || a === 'trem2' || a === 'trem3');
    if (tr) orn.push(`<tremolo type="single">${tr === 'trem' ? 1 : tr === 'trem2' ? 2 : 3}</tremolo>`);
    if (orn.length) parts.push(`<ornaments>${orn.join('')}</ornaments>`);
    const tm = ev.tup && TUPM.get(ev);
    if (tm === 'start') parts.push(`<tuplet type="start" bracket="yes"/>`);
    if (tm === 'stop') parts.push('<tuplet type="stop"/>');
  }
  return parts.length ? `<notations>${parts.join('')}</notations>` : '';
}

// ---------- compressed MusicXML (.mxl): a zip with the score and a container file ----------
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(bytes) { let c = 0xFFFFFFFF; for (let i = 0; i < bytes.length; i++) c = CRC[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
export async function zipFiles(files) {
  // files: [{ name, data: Uint8Array }]; deflate when the browser can, else store
  const enc = new TextEncoder();
  const chunks = [], central = [];
  let offset = 0;
  for (const f of files) {
    const name = enc.encode(f.name);
    const crc = crc32(f.data);
    let body = f.data, method = 0;
    if (typeof CompressionStream !== 'undefined' && f.name !== 'mimetype') {
      try { const cs = new Blob([f.data]).stream().pipeThrough(new CompressionStream('deflate-raw')); body = new Uint8Array(await new Response(cs).arrayBuffer()); method = 8; } catch { body = f.data; method = 0; }
    }
    const head = new DataView(new ArrayBuffer(30));
    head.setUint32(0, 0x04034b50, true); head.setUint16(4, 20, true); head.setUint16(6, 0, true); head.setUint16(8, method, true);
    head.setUint16(10, 0, true); head.setUint16(12, 0x21, true); head.setUint32(14, crc, true); head.setUint32(18, body.length, true); head.setUint32(22, f.data.length, true);
    head.setUint16(26, name.length, true); head.setUint16(28, 0, true);
    chunks.push(new Uint8Array(head.buffer), name, body);
    const cen = new DataView(new ArrayBuffer(46));
    cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true); cen.setUint16(8, 0, true); cen.setUint16(10, method, true);
    cen.setUint16(12, 0, true); cen.setUint16(14, 0x21, true); cen.setUint32(16, crc, true); cen.setUint32(20, body.length, true); cen.setUint32(24, f.data.length, true);
    cen.setUint16(28, name.length, true); cen.setUint32(42, offset, true);
    central.push(new Uint8Array(cen.buffer), name);
    offset += 30 + name.length + body.length;
  }
  const cenSize = central.reduce((a, c) => a + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true); end.setUint32(12, cenSize, true); end.setUint32(16, offset, true);
  return new Blob([...chunks, ...central, new Uint8Array(end.buffer)], { type: 'application/vnd.recordare.musicxml' });
}
export async function toMXL(score) {
  const enc = new TextEncoder();
  const container = '<?xml version="1.0" encoding="UTF-8"?>\n<container><rootfiles><rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>';
  return zipFiles([
    { name: 'mimetype', data: enc.encode('application/vnd.recordare.musicxml') },
    { name: 'META-INF/container.xml', data: enc.encode(container) },
    { name: 'score.musicxml', data: enc.encode(toMusicXML(score)) },
  ]);
}

// One part on its own, as a score: that instrument's staves and the lines that belong to them.
export function partScore(score, pi) {
  const part = score.parts[pi];
  const ids = new Set(part.staves.map((st) => st.id));
  return { ...score, parts: [part], spans: (score.spans || []).filter((sp) => !sp.st || ids.has(sp.st)) };
}
// The score and every part, each as its own .mxl, together in one .zip.
export async function toPartsZip(score, base = 'Score') {
  const clean = (t) => String(t || '').replace(/[\\/:*?"<>|]+/g, '').trim() || 'Part';
  const files = [];
  const blobBytes = async (b) => new Uint8Array(await b.arrayBuffer());
  files.push({ name: clean(base) + ' (score).mxl', data: await blobBytes(await toMXL(score)) });
  const used = new Set();
  for (let i = 0; i < score.parts.length; i++) {
    let n = clean(base) + ' - ' + clean(score.parts[i].name); while (used.has(n)) n += ' ' + (i + 1); used.add(n);
    files.push({ name: n + '.mxl', data: await blobBytes(await toMXL(partScore(score, i))) });
  }
  const z = await zipFiles(files);
  return new Blob([z], { type: 'application/zip' });
}

// ---------- import ----------
export async function unzip(buf) {
  const dv = new DataView(buf); const files = {};
  let eocd = buf.byteLength - 22; while (eocd >= 0 && dv.getUint32(eocd, true) !== 0x06054b50) eocd--;
  if (eocd < 0) throw new Error('Not a zip file');
  const n = dv.getUint16(eocd + 10, true); let p = dv.getUint32(eocd + 16, true);
  const dec = new TextDecoder();
  for (let i = 0; i < n; i++) {
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
    const name = dec.decode(new Uint8Array(buf, p + 46, nlen));
    p += 46 + nlen + xlen + clen;
    if (name.endsWith('/') || (method !== 0 && method !== 8)) continue;
    const lnlen = dv.getUint16(off + 26, true), lxlen = dv.getUint16(off + 28, true);
    const data = new Uint8Array(buf, off + 30 + lnlen + lxlen, csize);
    try { files[name] = method === 0 ? data : new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer()); } catch { /* (one damaged entry: the others are still read) */ }
  }
  return files;
}
// The text of an XML file in whatever encoding it was saved in: UTF-8, UTF-16 (Finale and some
// Windows programs write it, with or without the mark at the start) or an older one it names.
export function decodeXml(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let enc = 'utf-8';
  if (b[0] === 0xFF && b[1] === 0xFE) enc = 'utf-16le';
  else if (b[0] === 0xFE && b[1] === 0xFF) enc = 'utf-16be';
  else if (b[0] === 0x3C && b[1] === 0x00) enc = 'utf-16le';
  else if (b[0] === 0x00 && b[1] === 0x3C) enc = 'utf-16be';
  else if (!(b[0] === 0xEF && b[1] === 0xBB && b[2] === 0xBF)) {
    const head = String.fromCharCode(...b.subarray(0, 200));
    const m = /^<\?xml[^>]*encoding\s*=\s*["']([A-Za-z0-9._-]+)["']/.exec(head);
    // (a file that says UTF-16 while its bytes are plain text is read as it really is)
    if (m && !/^utf-?(8|16)/i.test(m[1])) { try { new TextDecoder(m[1]); enc = m[1]; } catch {} }
  }
  let s = new TextDecoder(enc).decode(b);
  if (s.charCodeAt(0) === 0xFEFF) s = s.slice(1);
  // (the encoding named at the top no longer says what it is: it is text now)
  return s.replace(/^(<\?xml[^>]*?)\s+encoding\s*=\s*["'][^"']*["']/, '$1');
}
export async function readMusicFile(file) {
  const buf = await file.arrayBuffer();
  const head = new Uint8Array(buf, 0, Math.min(4, buf.byteLength));
  const name = String((file && file.name) || '');
  if (!buf.byteLength) throw new Error('This file is empty.');
  let xml;
  if (head[0] === 0x50 && head[1] === 0x4b) {
    let files;
    try { files = await unzip(buf); } catch { throw new Error('This compressed file could not be opened. Export it again as MusicXML (.mxl or .musicxml).'); }
    const names = Object.keys(files);
    if (/\.mscz$/i.test(name) || names.some((k) => /\.mscx$/i.test(k))) throw new Error('This is a MuseScore file. In MuseScore, choose File › Export › MusicXML, then open that file here.');
    let path = null;
    const cont = names.find((k) => /^META-INF\/container\.xml$/i.test(k));
    if (cont) {
      const m = decodeXml(files[cont]).match(/full-path\s*=\s*["']([^"']+)["']/);
      if (m) { const want = decodeURIComponent(m[1]).replace(/^\.?\//, ''); path = names.find((k) => k === want) || names.find((k) => k.toLowerCase() === want.toLowerCase()) || null; }
    }
    if (!path) path = names.find((k) => /\.(musicxml|xml)$/i.test(k) && !/^META-INF\//i.test(k) && !/(^|\/)\./.test(k)) || null;
    if (!path || !files[path]) throw new Error('No MusicXML score was found inside this file.');
    xml = decodeXml(files[path]);
  } else {
    // a MIDI file: read too (notes on the nearest sixteenth or triplet)
    if (head[0] === 0x4D && head[1] === 0x54 && head[2] === 0x68 && head[3] === 0x64) { globalThis.__guessInst = guessInst; const R = await import('./midiread.js'); return migrateScore(R.fromMidi(buf, name)); }
    if (head[0] === 0x25 && head[1] === 0x50 && head[2] === 0x44 && head[3] === 0x46) throw new Error('This is a PDF. Add it to your library to read it, or open a MusicXML file here.');
    xml = decodeXml(buf);
  }
  return fromMusicXML(xml);
}
// A score written measure by measure (each measure holding every part) is turned around, part by
// part, as most programs write it.
function partwise(doc) {
  const tw = doc.documentElement;
  if (!tw || tw.tagName !== 'score-timewise') return doc;
  const out = document.implementation.createDocument(null, 'score-partwise', null);
  const root = out.documentElement;
  for (const a of tw.attributes) root.setAttribute(a.name, a.value);
  const parts = new Map();
  for (const ch of [...tw.children]) {
    if (ch.tagName !== 'measure') { root.append(out.importNode(ch, true)); continue; }
    for (const p of [...ch.children]) {
      if (p.tagName !== 'part') continue;
      const id = p.getAttribute('id');
      if (!parts.has(id)) { const pe = out.createElement('part'); pe.setAttribute('id', id); parts.set(id, pe); }
      const me = out.createElement('measure');
      for (const a of ch.attributes) me.setAttribute(a.name, a.value);
      for (const c of [...p.children]) me.append(out.importNode(c, true));
      parts.get(id).append(me);
    }
  }
  for (const pe of parts.values()) root.append(pe);
  return out;
}
// "3+2" beats (an additive time) count as 5
const beatsOf = (s) => String(s || '').split('+').reduce((a, x) => a + (parseInt(x, 10) || 0), 0) || 4;
// A length (in ticks) as a written value: a plain one, a dotted one, or a note of a tuplet (when the
// file gives a duration that no plain value has, and no note type, or a type that does not match).
const TUP_TRY = [[3, 2], [5, 4], [6, 4], [7, 4], [9, 8], [5, 2], [7, 8], [2, 3], [4, 3], [10, 8], [11, 8], [12, 8], [13, 8], [15, 8], [6, 5]];
// Rests for a gap that plain values cannot fill (beside a tuplet cut short, a tuplet shared between
// two staves): rests of that tuplet, then plain ones for what is left.
const TUP_UNITS = [40, 80, 160, 320, 640, 48, 96, 192, 384, 24, 20, 64, 128];
function gapRests(p, g, time) {
  if (g <= 0) return [];
  if (g % 15 === 0) return restsFor(p, g, time);
  const v = valueFor(g);
  if (v && v.tup && g >= 20) return [{ id: newId(), rest: true, t: v.t, dots: v.dots, tup: v.tup, keep: true }];
  for (const u of TUP_UNITS) {
    const uv = valueFor(Math.round(u)); if (!uv || !uv.tup) continue;
    for (let k = Math.floor(g / u); k >= 1; k--) {
      const left = Math.round(g - k * u);
      if (left < 0 || left % 15) continue;
      const tr = Array.from({ length: k }, () => ({ id: newId(), rest: true, t: uv.t, dots: uv.dots, tup: { ...uv.tup }, keep: true }));
      return [...tr, ...restsFor(p + Math.round(k * u), left, time)];
    }
  }
  // (what is left is rounding in the file: the nearest length that can be written)
  return restsFor(p, Math.round(g / 15) * 15, time);
}
function valueFor(d) {
  const v = valueOf(d); if (v) return v;
  for (const [n, m] of TUP_TRY) {
    const base = (d * n) / m, r = Math.round(base);
    if (Math.abs(base - r) > 0.5) continue;
    const b = valueOf(r); if (b) return { t: b.t, dots: b.dots, tup: { n, m, base: b.t } };
  }
  return null;
}
// Which instrument a part is, from its name in any of the usual languages (the most particular
// names first: a bass clarinet is not a clarinet, a violoncello is not a violin, a bass drum is not a bass).
const INST_WORDS = [
  ['piccolotrumpet', ['piccolo trumpet']], ['piccolo', ['piccolo', 'ottavino', 'petite flute', 'kleine flote', 'picc']],
  ['altoflute', ['alto flute', 'flauto contralto', 'altflote']], ['bassflute', ['bass flute', 'bassflote']],
  ['flute', ['flute', 'flauto', 'flauti', 'flote', 'flauta', 'fl.']],
  ['sopranorecorder', ['soprano recorder', 'descant recorder', 'sopranblockflote']], ['tenorrecorder', ['tenor recorder']], ['bassrecorder', ['bass recorder']], ['recorder', ['recorder', 'blockflote', 'flauto dolce', 'flute a bec']],
  ['oboedamore', ['oboe d\'amore', 'oboe d’amore', 'oboe damore']], ['englishhorn', ['english horn', 'cor anglais', 'corno inglese', 'englischhorn', 'corno ingles']],
  ['oboe', ['oboe', 'oboi', 'hautbois', 'ob.']],
  ['contrabassclarinet', ['contrabass clarinet', 'kontrabassklarinette']], ['bassclarinet', ['bass clarinet', 'clarinetto basso', 'bassklarinette', 'clarinette basse', 'clarinete bajo', 'b. cl']], ['altoclarinet', ['alto clarinet']], ['bassethorn', ['basset horn', 'corno di bassetto', 'bassetthorn']],
  ['clarinet', ['clarinet', 'clarinetto', 'clarinetti', 'klarinette', 'clarinette', 'clarinete', 'cl.']],
  ['contrabassoon', ['contrabassoon', 'contrafagotto', 'kontrafagott', 'contrebasson', 'double bassoon', 'cbsn']],
  ['bassoon', ['bassoon', 'fagott', 'fagotto', 'fagotti', 'basson', 'fagote', 'bsn']],
  ['sopsax', ['soprano sax']], ['altosax', ['alto sax']], ['tenorsax', ['tenor sax']], ['barisax', ['baritone sax', 'bari sax']], ['basssax', ['bass sax']],
  ['wagnertuba', ['wagner tuba']], ['flugelhorn', ['flugelhorn']], ['tenorhorn', ['tenor horn', 'tenorhorn', 'alto horn']],
  ['horn', ['horn', 'corno', 'corni', 'cor ', 'cors', 'trompa', 'hn.']],
  ['basstrumpet', ['bass trumpet', 'basstrompete']], ['cornet', ['cornet', 'cornetto', 'kornett']],
  ['trumpet', ['trumpet', 'tromba', 'trombe', 'trompete', 'trompette', 'trompeta', 'tpt']],
  ['basstrombone', ['bass trombone', 'bassposaune', 'b. trb', 'b trb']], ['altotrombone', ['alto trombone', 'altposaune']],
  ['trombone', ['trombone', 'tromboni', 'posaune', 'trb', 'tbn']],
  ['euphonium', ['euphonium']], ['cimbasso', ['cimbasso']], ['tuba', ['tuba']],
  ['timpani', ['timpani', 'pauke', 'timbales', 'timbal', 'timp']],
  ['glockenspiel', ['glockenspiel', 'campanelli', 'glock']], ['xylophone', ['xylophone', 'xilofono', 'xylophon', 'xylo']], ['vibraphone', ['vibraphone', 'vibrafono', 'vibraphon', 'vibes']], ['marimba', ['marimba']], ['tubularbells', ['tubular bells', 'chimes', 'campane', 'rohrenglocken']], ['crotales', ['crotales']], ['handbells', ['handbell']],
  ['snare', ['snare', 'side drum', 'tamburo', 'caisse claire', 'kleine trommel', 'caja']], ['bassdrum', ['bass drum', 'gran cassa', 'grosse caisse', 'grosse trommel', 'kick drum', 'bombo']],
  ['suspcymbal', ['suspended cymbal', 'splash', 'ride cymbal', 'piatto sospeso']], ['cymbals', ['cymbal', 'piatti', 'becken', 'cymbales', 'platillos']],
  ['triangle', ['triangle', 'triangolo', 'triangel', 'triangulo']], ['tambourine', ['tambourine', 'tamburello', 'tamburin', 'pandereta']], ['woodblock', ['wood block', 'woodblock', 'holzblock']], ['tomtoms', ['tom-tom', 'tom tom', 'toms']], ['castanets', ['castanet', 'castagnette', 'kastagnette']], ['congas', ['conga']], ['bongos', ['bongo']], ['drumset', ['drum set', 'drum kit', 'drumset', 'drums', 'batteria', 'schlagzeug']],
  ['harpsichord', ['harpsichord', 'cembalo', 'clavecin', 'clave']], ['celesta', ['celesta', 'celeste']], ['harmonium', ['harmonium']], ['organ', ['organ', 'orgel', 'organo', 'orgue', 'organo']], ['epiano', ['electric piano', 'e-piano', 'rhodes']], ['accordion', ['accordion', 'akkordeon', 'fisarmonica', 'accordeon', 'acordeon']], ['bandoneon', ['bandoneon']],
  ['piano', ['piano', 'klavier', 'pianoforte', 'fortepiano']],
  ['harp', ['harp', 'harfe', 'arpa', 'harpe']],
  ['bassguitar', ['bass guitar', 'electric bass', 'e-bass', 'bass gtr']], ['eguitar', ['electric guitar', 'e-guitar', 'e-gitarre']], ['steelguitar', ['acoustic guitar', 'steel guitar', 'steel-string']], ['twelvestring', ['12-string']],
  ['guitar', ['guitar', 'gitarre', 'chitarra', 'guitare', 'guitarra', 'gtr']], ['mandolin', ['mandolin']], ['banjo', ['banjo']], ['ukulele', ['ukulele']], ['theorbo', ['theorbo', 'tiorba']], ['lute', ['lute', 'laute', 'liuto', 'luth']],
  ['violadagamba', ['viola da gamba', 'gamba']], ['violone', ['violone']],
  ['contrabass', ['contrabass', 'double bass', 'kontrabass', 'contrebasse', 'contrabbasso', 'contrabajo', 'string bass', 'cb.', 'd.b.']],
  ['cello', ['violoncell', 'cello', 'vc.', 'vlc']],
  ['viola', ['viola', 'bratsche', 'vla', 'va.']],
  ['violin', ['violin', 'violino', 'violon', 'geige', 'vln', 'vl.']],
  ['mezzo', ['mezzo']], ['countertenor', ['countertenor', 'contratenor']], ['contralto', ['contralto']], ['soprano', ['soprano', 'sopran', 'canto']],
  ['alto', ['alto', 'alt ']], ['tenor', ['tenor', 'tenore']], ['baritone', ['baritone', 'bariton', 'baritono']], ['bass', ['bass', 'basso', 'bajo']],
  ['voice', ['voice', 'voce', 'vocal', 'stimme', 'voix', 'voz', 'singer', 'melody']],
  ['drumset', ['percussion', 'perc.', 'schlagwerk', 'percusion', 'percussioni']],
];
const ABBR = new Set(['picc', 'tpt', 'trb', 'tbn', 'bsn', 'cbsn', 'vla', 'vln', 'vlc', 'gtr', 'timp', 'xylo', 'toms', 'glock', 'kick']);
const norm = (x) => ' ' + String(x || '').toLowerCase().replace(/♭/g, 'b').replace(/♯/g, '#').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim() + ' ';
function guessInst(name, program, clefs, sure) {
  const n = norm(name);
  let best = null;
  // (the exact name first; else the longest name it begins with, as a whole word: "Violin II" is
  // not "Violin", "Bassoons" is not "Bass")
  if (n.trim()) best = INSTRUMENTS.find((i) => n === norm(i.name)) || null;
  // (a plural before a name it begins with: "Violini I" is the violins, not a violin)
  const plural = /\b(violins|violini|violons|violas|viole|cellos|violoncellos|violoncelli|violoncelles|contrabasses|double basses|kontrabasse|contrabassi)\b/.test(n);
  // (the instrument whose name it begins with, and the most particular word it holds: the longer one decides)
  let sw = null, swLen = 0, kw = null, kwLen = 0;
  if (n.trim() && !best && !plural) for (const i of INSTRUMENTS) { const w = norm(i.name).trimEnd(); if (n.startsWith(w) && /[\s\d.,(]/.test(n[w.length] || ' ') && w.length > swLen) { sw = i; swLen = w.length; } }
  // (a plural is a section: violins, violas, cellos, basses)
  if (!best) for (const [k, words] of [['violin1', ['violins', 'violini', 'violons']], ['violas', ['violas', 'viole', ' altos']], ['cellos', ['cellos', 'violoncellos', 'violoncelli', 'violoncelles']], ['contrabasses', ['contrabasses', 'double basses', 'kontrabasse', 'contrabassi']]]) {
    if (words.some((w) => n.includes(w))) { best = INST[k] && k === 'violin1' && /\b(ii|2)\b/.test(n) ? INST.violin2 : INST[k]; break; }
  }
  if (!best) for (const [k, words] of INST_WORDS) {
    if (!INST[k]) continue;
    const hit = words.find((w) => (ABBR.has(w) ? new RegExp('[\\s(]' + w + '[\\s.)\\d]').test(n) : n.includes(w)));
    if (hit) { kw = INST[k]; kwLen = hit.length; break; }
  }
  if (!best) best = sw && swLen >= kwLen ? sw : kw || sw;
  if (sure) return best;
  if (!best && program) { const sid = Object.entries(GM).find(([, v]) => v === program); if (sid) best = INSTRUMENTS.find((i) => i.sound === sid[0]); }
  if (!best) best = clefs >= 2 ? INST.piano : INST.violin;
  return best;
}
export function fromMusicXML(xmlText) {
  let doc = new DOMParser().parseFromString(xmlText, 'application/xml');
  if (doc.querySelector('parsererror')) {
    // (a stray character before the start, a stray "&", a DTD with its own names: tried once more without them)
    const fixed = String(xmlText).replace(/^[^<]+/, '').replace(/<!DOCTYPE[^>[]*(\[[\s\S]*?\])?\s*>/i, '').replace(/&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)/g, '&amp;');
    doc = new DOMParser().parseFromString(fixed, 'application/xml');
    if (doc.querySelector('parsererror')) throw new Error('This file is not MusicXML, or it is damaged.');
  }
  const rootTag = doc.documentElement ? doc.documentElement.tagName : '';
  if (rootTag === 'mei') throw new Error('This is an MEI file. Open a MusicXML file (.musicxml or .mxl) here.');
  if (rootTag !== 'score-partwise' && rootTag !== 'score-timewise') throw new Error('This file is not MusicXML.');
  doc = partwise(doc);
  for (const k of Object.keys(TUPC)) delete TUPC[k];
  const lyrNames = new Map();
  const q = (el, sel) => el.querySelector(sel);
  const txt = (el, sel) => { const e = sel ? q(el, sel) : el; return e ? e.textContent.trim() : ''; };
  const title = txt(doc, 'work > work-title') || txt(doc, 'movement-title') || txt(doc, 'credit-words') || 'Imported score';
  const composer = txt(doc, 'creator[type="composer"]');
  const lyricist = txt(doc, 'creator[type="lyricist"]') || txt(doc, 'creator[type="poet"]'), arranger = txt(doc, 'creator[type="arranger"]'), rights = txt(doc, 'identification > rights');
  const partEls = [...doc.querySelectorAll('score-partwise > part')].filter((p) => p.querySelector(':scope > measure'));
  if (!partEls.length) throw new Error('There is no music in this file.');
  const listEls = Object.fromEntries([...doc.querySelectorAll('part-list > score-part')].map((sp) => [sp.getAttribute('id'), sp]));
  // a part called only "1 2" or "3" inside a group named "Horns in F": "Horns in F 1 2"
  const groupOf = {};
  { const open = new Map(); for (const e of [...(doc.querySelector('part-list') || { children: [] }).children]) {
      if (e.tagName === 'part-group') { const n = e.getAttribute('number') || '1'; if (e.getAttribute('type') === 'start') open.set(n, (e.querySelector('group-name') || {}).textContent || ''); else open.delete(n); }
      else if (e.tagName === 'score-part') { const names = [...open.values()].filter((x) => x && x.trim()); if (names.length) groupOf[e.getAttribute('id')] = names[names.length - 1].trim(); } } }
  const score = newScore({ title, composer, insts: ['piano'], bars: 1 });
  score.parts = []; score.measures = [];
  if (lyricist) score.lyricist = lyricist; if (arranger) score.arranger = /^arr/i.test(arranger) ? arranger : 'arr. ' + arranger; if (rights) score.rights = rights;
  const nMeasures = Math.max(...partEls.map((p) => p.querySelectorAll(':scope > measure').length));
  for (let m = 0; m < nMeasures; m++) score.measures.push({});
  // (which part states the time and the key of each measure: the first that does)
  const timeOwner = [], keyOwner = [];
  // a transposing part: written to sounding, octaves included (piccolo, guitar, double bass, glockenspiel)
  const trOf = (t) => { const oc = +txt(t, 'octave-change') || 0; return { steps: (+txt(t, 'diatonic') || 0) + 7 * oc, semis: (+txt(t, 'chromatic') || 0) + 12 * oc }; };
  const firstDiv = (pel) => { const d = pel.querySelector('measure attributes divisions'); return (d && +d.textContent) || 1; };
  // how long each measure really is, in every part (a pickup bar, a shorter bar at a repeat or at
  // the end, a bar longer than its time, music with no time signature at all)
  {
    const lens = new Array(nMeasures).fill(0), implicit = new Array(nMeasures).fill(false), times = [];
    timeOwner.length = 0; keyOwner.length = 0;
    partEls.forEach((pel, pi) => {
      let div = firstDiv(pel), tm = [4, 4];
      [...pel.querySelectorAll(':scope > measure')].forEach((mel, m) => {
        if (mel.getAttribute('implicit') === 'yes') implicit[m] = true;
        let pos = 0, end = 0;
        const d = (el) => ((+txt(el, 'duration') || 0) * 480) / div;
        for (const el of mel.children) {
          const t = el.tagName;
          if (t === 'attributes') {
            const dv = q(el, 'divisions'); if (dv) div = +dv.textContent || div;
            const tb = q(el, 'time beats'); if (tb) { tm = [beatsOf(tb.textContent), +txt(el, 'time beat-type') || 4]; if (timeOwner[m] === undefined) timeOwner[m] = pi; }
            if (q(el, 'key fifths') && keyOwner[m] === undefined) keyOwner[m] = pi;
          }
          else if (t === 'backup') pos = Math.max(0, pos - d(el));
          else if (t === 'forward') { pos += d(el); end = Math.max(end, pos); }
          else if (t === 'note') {
            if (q(el, 'grace') || q(el, 'chord')) continue;
            const r = q(el, 'rest'), len = d(el);
            if (!(r && r.getAttribute('measure') === 'yes')) end = Math.max(end, pos + len);
            pos += len;
          }
        }
        lens[m] = Math.max(lens[m], Math.round(end));
        if (pi === (timeOwner[m] ?? 0) || !times[m]) times[m] = tm.slice();
      });
    });
    const noTime = !doc.querySelector('time beats');
    if (noTime) score.measures[0].timeHide = true;
    for (let m = 0; m < nMeasures; m++) {
      const tm = times[m] || times[m - 1] || [4, 4], full = (tm[0] * WHOLE) / tm[1], L = lens[m];
      if (!L) continue;
      // (a bar a little too long is a mistake in the file, not a longer bar; lengths go to the
      // nearest 128th, so the bar can always be written)
      const R = Math.abs(L - Math.round(L / 15) * 15) <= 5 ? Math.round(L / 15) * 15 : L;
      if (noTime ? Math.abs(R - full) > 2 : R > full + 60) score.measures[m].len = R;
      else if (implicit[m] && R < full - 2) { if (m === 0) score.measures[0].pickup = R; else score.measures[m].len = R; }
    }
    // (a last bar that completes the pickup bar)
    const last = nMeasures - 1, tl = times[last] || [4, 4], fl = (tl[0] * WHOLE) / tl[1];
    if (last > 0 && score.measures[0].pickup && !score.measures[last].len && lens[last] > 0 && Math.abs(lens[last] + score.measures[0].pickup - fl) <= 2) score.measures[last].len = lens[last];
  }
  partEls.forEach((pel, pi) => {
    lyrNames.clear();
    const sp = listEls[pel.getAttribute('id')];
    let pname = (sp ? txt(sp, 'part-name') : '').replace(/\s+/g, ' ').trim();
    const gname = groupOf[pel.getAttribute('id')] || '', iname = sp ? txt(sp, 'score-instrument instrument-name') : '';
    if (/^[\dIVXivx.,&+\- ]*$/.test(pname)) pname = ((gname || iname) + ' ' + pname).trim();
    if (!pname) pname = 'Part ' + (pi + 1);
    const program = sp ? +txt(sp, 'midi-program') || 0 : 0;
    // (as many staves as the part says, or as its music uses)
    const nSt = Math.min(6, Math.max(1, ...[...pel.querySelectorAll('measure attributes staves')].map((e) => +e.textContent || 1), ...[...pel.querySelectorAll('measure > note > staff, measure > direction > staff, measure > harmony > staff')].map((e) => +e.textContent || 1)));
    let inst = guessInst(pname, program, nSt, true);
    if (!inst && iname) inst = guessInst(iname, program, nSt, true);
    if (!inst) inst = guessInst(pname, program, nSt);
    const part = newPart(inst.id);
    part.name = pname || inst.name; part.abbr = (sp && txt(sp, 'part-abbreviation')) || inst.abbr;
    // the staves come from the file
    part.staves = Array.from({ length: nSt }, (_, i) => ({ id: newId(), clef: inst.clefs[i] || (i > 0 && nSt === 2 ? 'bass' : inst.clefs[0]), bars: [] }));
    score.parts.push(part);
    let divisions = firstDiv(pel), tr = { steps: 0, semis: 0 }, trSeen = false;
    const partBeams = !!pel.querySelector('note > beam');
    let time = [4, 4];
    const measureEls = [...pel.querySelectorAll(':scope > measure')];
    // marks waiting for the next note on a staff, lines being drawn, the last note on a staff
    const pend = part.staves.map(() => ({}));
    const openSpans = [];
    const lastAt = part.staves.map(() => null);
    score.spans = score.spans || [];
    for (let m = 0; m < nMeasures; m++) {
      const mel = measureEls[m];
      const perStaff = part.staves.map(() => []);   // {pos, ev}
      // (up to four voices on each staff: the first one met is voice 1, the others 2, 3 and 4 in turn)
      const perStaffV = part.staves.map(() => ({ 2: [], 3: [], 4: [] }));
      const voiceOf = part.staves.map(() => null);
      const extraV = part.staves.map(() => ({}));
      const vMap = part.staves.map(() => new Map());
      let pos = 0, lastStart = 0;
      const ms = score.measures[m];
      if (mel) for (const el of mel.children) {
        const tag = el.tagName;
        if (tag === 'attributes') {
          if (q(el, 'divisions')) divisions = +txt(el, 'divisions') || 1;
          if (q(el, 'key fifths') && pi === (keyOwner[m] ?? 0)) {
            // a transposing first part (clarinet, horn…) writes its own key: the score keeps the sounding key
            const t = q(el, 'transpose') ? trOf(q(el, 'transpose')) : tr;
            let k = +txt(el, 'key fifths') + ((t.steps || t.semis) ? fifthsOfInterval(t.steps, t.semis) : 0);
            while (k > 7) k -= 12; while (k < -7) k += 12;
            ms.key = k;
          }
          if (q(el, 'time beats') && pi === (timeOwner[m] ?? 0)) {
            time = [beatsOf(txt(el, 'time beats')), +txt(el, 'time beat-type') || 4];
            const sym = q(el, 'time') && q(el, 'time').getAttribute('symbol');
            // (a time stated again, the same as before, is not a change)
            const before = m > 0 ? timeAt(score, m - 1) : null;
            if (!before || before[0] !== time[0] || before[1] !== time[1] || (sym || '') !== ((score.measures.slice(0, m).reverse().find((x) => x.time) || {}).timeSym || '')) { ms.time = time.slice(); if (sym === 'common' || sym === 'cut') ms.timeSym = sym; }
            if (q(el, 'time').getAttribute('print-object') === 'no') ms.timeHide = true;
          }
          else if (q(el, 'time beats')) time = [beatsOf(txt(el, 'time beats')), +txt(el, 'time beat-type') || 4];
          for (const c of el.querySelectorAll('clef')) {
            const k = (+c.getAttribute('number') || 1) - 1; if (!part.staves[k]) continue;
            const sign = txt(c, 'sign'), line = +txt(c, 'line'), oct = +txt(c, 'clef-octave-change') || 0;
            const clef = sign === 'G' ? (line === 1 ? 'frenchviolin' : oct < 0 ? 'treble8' : oct > 0 ? 'treble8va' : 'treble') : sign === 'F' ? (line === 3 ? 'baritoneF' : oct < 0 ? 'bass8' : oct > 0 ? 'bass8va' : 'bass') : sign === 'C' ? ({ 1: 'soprano', 2: 'mezzo', 4: 'tenor', 5: 'baritoneC' }[line] || 'alto') : sign === 'percussion' ? 'perc' : 'treble';
            // (in the middle of the bar: on the next note, and in force from the next bar on)
            if (pos > 0) { pend[k].clef = clef; part.staves[k].clefs = part.staves[k].clefs || {}; part.staves[k].clefs[m + 1] = clef; }
            else if (m === 0) part.staves[k].clef = clef; else { part.staves[k].clefs = part.staves[k].clefs || {}; part.staves[k].clefs[m] = clef; }
          }
          // (one line for a drum or a cymbal; five when the file has five for it)
          if (m === 0) for (const sd of el.querySelectorAll('staff-details')) {
            const k = (+sd.getAttribute('number') || 1) - 1, nl = +txt(sd, 'staff-lines'); if (!part.staves[k] || !nl) continue;
            const it = M0.instOf(part);
            if (nl === 1 && it.unpitched) part.staves[k].lines = 1; else if (nl === 5 && it.lines === 1) part.staves[k].lines = 5;
          }
          if (q(el, 'transpose')) { tr = trOf(q(el, 'transpose')); if (!trSeen) { trSeen = true; const it = inst.tr || { steps: 0, semis: 0 }; if ((it.steps || 0) !== tr.steps || (it.semis || 0) !== tr.semis) part.tr = { ...tr }; } }
        // (the place in the bar is kept exact, and rounded to ticks only where a note is put)
        } else if (tag === 'backup') pos = Math.max(0, pos - (+txt(el, 'duration') * 480) / divisions);
        else if (tag === 'forward') pos += (+txt(el, 'duration') * 480) / divisions;
        else if (tag === 'barline') {
          if (q(el, 'repeat[direction="forward"]')) ms.start = 'repeat';
          if (q(el, 'repeat[direction="backward"]')) ms.bar = 'repeat';
          else if (txt(el, 'bar-style') === 'light-light') ms.bar = 'double';
          const en = q(el, 'ending');
          if (en && pi === 0) {
            const type = en.getAttribute('type'), n = parseInt(en.getAttribute('number'), 10) || 1;
            if (type === 'start') openSpans.push({ id: newId(), kind: 'volta', n, a: { m, pos: 0 }, b: null });
            else { const v = openSpans.find((x) => x.kind === 'volta' && !x.b); if (v) { v.b = { m, pos: 0 }; if (type === 'discontinue') v.closed = false; score.spans.push(v); openSpans.splice(openSpans.indexOf(v), 1); } }
          }
        } else if (tag === 'harmony') {
          const k = Math.max(0, (+txt(el, 'staff') || 1) - 1);
          const ra = +txt(el, 'root root-alter') || 0, ba = +txt(el, 'bass bass-alter') || 0;
          const kd = q(el, 'kind'); const kt = kd ? (kd.getAttribute('text') ?? (KINDS.find(([, v]) => v === kd.textContent.trim()) || [''])[0]) : '';
          (pend[k] || pend[0]).chord = txt(el, 'root root-step') + (ra > 0 ? '#' : ra < 0 ? 'b' : '') + kt + (q(el, 'bass') ? '/' + txt(el, 'bass bass-step') + (ba > 0 ? '#' : ba < 0 ? 'b' : '') : '');
        } else if (tag === 'direction') {
          const k = Math.max(0, (+txt(el, 'staff') || 1) - 1); const P = pend[k] || pend[0];
          const pm = q(el, 'per-minute'); const snd = q(el, 'sound[tempo]');
          const words = txt(el, 'words');
          if ((pm || snd) && pi === 0) ms.tempo = { bpm: Math.round(+(pm ? pm.textContent : snd.getAttribute('tempo'))) || 96, beat: { half: 2, eighth: 8 }[txt(el, 'beat-unit')] || 4, text: words };
          else if (q(el, 'segno') && pi === 0) ms.mark = 'segno';
          else if (q(el, 'coda') && pi === 0) ms.mark = 'coda';
          else if (q(el, 'rehearsal') && pi === 0) ms.rehearsal = txt(el, 'rehearsal');
          else if (q(el, 'dynamics')) { const d = q(el, 'dynamics').firstElementChild; if (d) P.dyn = d.tagName; }
          else if (q(el, 'wedge')) { const ty = q(el, 'wedge').getAttribute('type'); P.hp = ty === 'crescendo' ? '<' : ty === 'diminuendo' ? '>' : 'end'; }
          else if (q(el, 'octave-shift')) {
            const os = q(el, 'octave-shift'), ty = os.getAttribute('type'), size = +os.getAttribute('size') || 8;
            if (ty === 'stop') { const sp = openSpans.find((x) => /^(8v|15m)/.test(x.kind) && x.k === k && !x.b); if (sp) { sp.b = lastAt[k] || { m, pos: 0 }; delete sp.k; score.spans.push(sp); openSpans.splice(openSpans.indexOf(sp), 1); } }
            else openSpans.push({ id: newId(), kind: size === 15 ? (ty === 'down' ? '15ma' : '15mb') : (ty === 'down' ? '8va' : '8vb'), st: part.staves[k].id, k, a: null, b: null });
          } else if (q(el, 'pedal')) {
            const pd = q(el, 'pedal'), ty = pd.getAttribute('type');
            if (ty === 'start') openSpans.push({ id: newId(), kind: 'ped', st: part.staves[k].id, k, a: null, b: null, ...(pd.getAttribute('line') === 'no' ? { line: false } : {}) });
            else if (ty === 'stop') { const sp = openSpans.find((x) => x.kind === 'ped' && x.k === k && !x.b); if (sp) { sp.b = lastAt[k] || { m, pos: 0 }; delete sp.k; score.spans.push(sp); openSpans.splice(openSpans.indexOf(sp), 1); } }
          } else if (q(el, 'dashes')) {
            const ty = q(el, 'dashes').getAttribute('type');
            const kind = /rit|rall/i.test(words) ? 'rit' : /accel/i.test(words) ? 'accel' : /cresc/i.test(words) ? 'cresc' : /dim|decresc/i.test(words) ? 'dim' : null;
            if (ty === 'start' && kind) openSpans.push({ id: newId(), kind, st: part.staves[k].id, k, a: null, b: null });
            if (ty === 'stop') { const sp = openSpans.find((x) => ['rit', 'accel', 'cresc', 'dim'].includes(x.kind) && x.k === k && !x.b); if (sp) { sp.b = lastAt[k] || { m, pos: 0 }; delete sp.k; score.spans.push(sp); openSpans.splice(openSpans.indexOf(sp), 1); } }
          } else if (words) {
            const jump = Object.entries(JUMP_WORDS).find(([, w]) => w.toLowerCase() === words.toLowerCase());
            if (jump && pi === 0) ms.jump = jump[0];
            else { const we = q(el, 'words'); P.txt = words; P.txtStyle = we.getAttribute('enclosure') ? 'box' : we.getAttribute('font-style') === 'italic' ? 'expr' : 'tech'; }
          }
        } else if (tag === 'note') {
          if (q(el, 'grace')) {
            // keep the first grace note before a note; it is drawn small and played just before the beat
            const kg = Math.max(0, (+txt(el, 'staff') || 1) - 1);
            if (!q(el, 'chord') && !q(el, 'rest') && pend[kg]) {
              const step = STEP_NAMES.indexOf(txt(el, 'pitch step') || 'C'), oct = +(txt(el, 'pitch octave') || 4), alter = Math.round(+txt(el, 'pitch alter') || 0);
              let gn = { s: oct * 7 + Math.max(0, step), a: alter };
              if (tr.steps || tr.semis) { const s2 = gn.s + tr.steps; const mid = midiOf(gn.s, gn.a) + tr.semis; gn = { s: s2, a: mid - midiOf(s2, 0) }; }
              const g = { ...gn, ...(q(el, 'grace').getAttribute('slash') === 'yes' ? {} : { slash: false }), ...(q(el, 'accidental') ? { acc: alter } : {}) };
              // (a group of grace notes: the first, then the others in turn, up to eight)
              if (!pend[kg].grace) pend[kg].grace = g; else { pend[kg].graceMore = pend[kg].graceMore || []; if (pend[kg].graceMore.length < 7) pend[kg].graceMore.push({ s: g.s, a: g.a, ...(g.acc !== undefined ? { acc: g.acc } : {}) }); }
            }
            continue;
          }
          const k = Math.min(part.staves.length, Math.max(1, +txt(el, 'staff') || 1)) - 1;
          if (!part.staves[k]) continue;
          const voice = txt(el, 'voice') || '1';
          if (voiceOf[k] === null) voiceOf[k] = voice;
          if (voice !== voiceOf[k] && !vMap[k].has(voice) && vMap[k].size < 3) vMap[k].set(voice, vMap[k].size + 2);
          const durF = ((+txt(el, 'duration') || 0) * 480) / divisions;
          const isChord = !!q(el, 'chord');
          const start = Math.round(isChord ? lastStart : pos);
          const dur = Math.round((isChord ? lastStart : pos) + durF) - start;
          if (!isChord) { lastStart = pos; pos += durF; }
          // (a fifth voice or more on one staff: its notes go wherever there is room, below)
          const over = voice !== voiceOf[k] && !vMap[k].has(voice);
          const inV2 = voice !== voiceOf[k], vNo = inV2 && !over ? vMap[k].get(voice) : 1;
          const list = over ? (extraV[k][voice] = extraV[k][voice] || []) : inV2 ? perStaffV[k][vNo] : perStaff[k];
          const type = TYPE_BACK[txt(el, 'type')];
          const dots = el.querySelectorAll('dot').length;
          const tm = q(el, 'time-modification');
          let ev = { id: newId(), t: type || 4, dots, rest: !!q(el, 'rest') };
          if (!type) { const v = valueOf(dur); if (v) { ev.t = v.t; ev.dots = v.dots; } }
          if (q(el, 'rest') && q(el, 'rest').getAttribute('measure') === 'yes') ev = { id: newId(), rest: true, full: true, t: 1, dots: 0 };
          if (tm) ev.tup = { n: +txt(tm, 'actual-notes') || 3, m: +txt(tm, 'normal-notes') || 2, base: ev.t };
          // (a cue: another part's notes, small and not played; small notes, played)
          if ([...el.children].some((c) => c.tagName === 'cue')) ev.cue = true;
          else if (q(el, 'type') && q(el, 'type').getAttribute('size') === 'cue') ev.small = true;
          // the duration in the file decides when the note type does not match it (or there is none):
          // the value that has that length, a note of a tuplet, or, when nothing has it, tied notes
          let drop = false, split = false;
          if (!ev.full && dur > 0 && !isChord && Math.abs(evTicks(ev) - dur) > 2) {
            const v = valueFor(dur) || valueFor(dur + 1) || valueFor(dur - 1) || valueFor(dur + 2) || valueFor(dur - 2);
            // (the file's own tuplet, when it is the one found)
            if (v && !(v.tup && ev.tup && v.tup.n === ev.tup.n && v.tup.m === ev.tup.m && v.t === ev.t)) { ev.t = v.t; ev.dots = v.dots; if (v.tup) ev.tup = v.tup; else delete ev.tup; }
            else if (!v) { if (ev.rest) drop = true; else split = true; }
          }
          if (ev.tup) {
            // each note's place in its group (so septuplets and the like add up exactly)
            if (!isChord) { const key = k + ':' + voice, c = TUPC[key]; ev.tup.i = c && c.n === ev.tup.n && c.i < ev.tup.n - 1 ? c.i + 1 : 0; TUPC[key] = { n: ev.tup.n, i: ev.tup.i }; }
          } else if (!isChord) delete TUPC[k + ':' + voice];
          if (!ev.rest) {
            const step = STEP_NAMES.indexOf(txt(el, 'pitch step') || txt(el, 'unpitched display-step') || 'C');
            const oct = +(txt(el, 'pitch octave') || txt(el, 'unpitched display-octave') || 4);
            const alter = Math.round(+txt(el, 'pitch alter') || 0);
            let n = { s: oct * 7 + Math.max(0, step), a: alter, tie: [...el.querySelectorAll('tie')].some((t) => t.getAttribute('type') === 'start') };
            if (tr.steps || tr.semis) { const s2 = n.s + tr.steps; const mid = midiOf(n.s, n.a) + tr.semis; n = { ...n, s: s2, a: mid - midiOf(s2, 0) }; }
            const nh = q(el, 'notehead');
            if (nh) { const hk = HEAD_BACK[(nh.textContent || '').trim()]; if (hk) n.head = hk; else if (nh.getAttribute('parentheses') === 'yes') n.head = 'ghost'; }
            ev.notes = [n];
            const arts = [];
            for (const [a, x] of Object.entries(ART_XML)) if (q(el, 'articulations ' + x)) arts.push(a);
            if (q(el, 'fermata')) arts.push('ferm');
            if (q(el, 'up-bow')) arts.push('up'); if (q(el, 'down-bow')) arts.push('down');
            const fe = q(el, 'fermata'); if (fe && fe.textContent.trim() === 'angled') { arts.splice(arts.indexOf('ferm'), 1); arts.push('fermS'); } else if (fe && fe.textContent.trim() === 'square') { arts.splice(arts.indexOf('ferm'), 1); arts.push('fermL'); }
            for (const [a, x] of Object.entries(ORN_XML)) if (q(el, 'ornaments ' + x)) arts.push(a);
            const trm = q(el, 'ornaments tremolo'); if (trm) { const n2 = +trm.textContent || 1; arts.push(n2 >= 3 ? 'trem3' : n2 === 2 ? 'trem2' : 'trem'); }
            if (q(el, 'arpeggiate')) arts.push('arp');
            if (q(el, 'technical stopped')) arts.push('stopped'); if (q(el, 'technical open-string')) arts.push('open'); if (q(el, 'technical snap-pizzicato')) arts.push('snap'); if (q(el, 'technical harmonic')) arts.push('harm');
            const wl = q(el, 'ornaments wavy-line');
            if (wl && wl.getAttribute('type') === 'start') { openSpans.push({ id: newId(), kind: 'trill', st: part.staves[k].id, k, a: { m, pos: start }, b: null }); const ti = arts.indexOf('trill'); if (ti >= 0) arts.splice(ti, 1); }
            if (wl && wl.getAttribute('type') === 'stop') { const sp = openSpans.find((x) => x.kind === 'trill' && x.k === k && !x.b); if (sp) { sp.b = { m, pos: start }; delete sp.k; score.spans.push(sp); openSpans.splice(openSpans.indexOf(sp), 1); } }
            const gl = q(el, 'glissando') || q(el, 'slide');
            if (gl && gl.getAttribute('type') === 'start') openSpans.push({ id: newId(), kind: 'gliss', st: part.staves[k].id, k, a: { m, pos: start }, b: null, g: 1 });
            if (gl && gl.getAttribute('type') === 'stop') { const sp = openSpans.find((x) => x.kind === 'gliss' && x.k === k && !x.b); if (sp) { sp.b = { m, pos: start }; delete sp.k; delete sp.g; score.spans.push(sp); openSpans.splice(openSpans.indexOf(sp), 1); } }
            if (arts.length) ev.art = [...new Set(arts)];
            const fgs = [...el.querySelectorAll('technical fingering')].map((x) => x.textContent.trim()).filter(Boolean); if (fgs.length) ev.fing = fgs.join(' ');
            { const sn = el.querySelector('technical string'); const k = sn ? parseInt(sn.textContent, 10) : 0; if (k >= 1 && k <= 4) ev.str = ['I', 'II', 'III', 'IV'][k - 1]; }
            // a note can end one slur and start the next
            const slT = [...el.querySelectorAll('slur')].map((x) => x.getAttribute('type'));
            if (slT.includes('start')) { ev.slur = 'start'; if (slT.includes('stop')) ev.slurEnd2 = true; } else if (slT.includes('stop')) ev.slur = 'end';
          } else delete ev.notes;
          // the beams as the file has them (when it has any): where one starts, notes joined, notes on their own
          if (!isChord && !ev.rest && ev.t >= 8 && partBeams) {
            const bm = q(el, 'beam[number="1"]') || q(el, 'beam'); const bv = bm ? bm.textContent.trim() : '';
            if (bv === 'begin') ev.beam = 'start'; else if (bv === 'continue' || bv === 'end') ev.beam = 'join'; else if (!bm) ev.nobeam = true;
          }
          if (isChord && !ev.rest) {
            const host = list.find((x) => x.pos === start && x.ev.notes);
            if (host) { host.ev.notes.push(ev.notes[0]); continue; }
          }
          // marks that were waiting for this note
          const P = pend[k];
          if (!isChord && !inV2) {
            for (const key of ['dyn', 'hp', 'txt', 'txtStyle', 'chord', 'clef']) if (P[key]) { ev[key] = P[key]; delete P[key]; }
            if (P.grace) { if (!ev.rest && ev.notes) { ev.grace = { ...P.grace, dir: P.grace.s > ev.notes[0].s ? 1 : -1 }; if (P.graceMore) ev.graceMore = P.graceMore; } delete P.grace; delete P.graceMore; }
            if (!ev.rest) {
              // each verse (lyric number 1, 2…; a name instead of a number keeps the order of the file)
              const lys = [...el.children].filter((c) => c.tagName === 'lyric');
              lys.forEach((ly, j) => {
                const nm = ly.getAttribute('number'); let v = parseInt(nm, 10);
                if (!(v >= 1) && !nm) v = j + 1;
                if (!(v >= 1)) { const key = nm; if (!lyrNames.has(key)) lyrNames.set(key, lyrNames.size + 1); v = lyrNames.get(key); }
                if (v > MAX_VERSES) return;
                const words = [...ly.children].filter((c) => c.tagName === 'text').map((c) => c.textContent.trim()).filter(Boolean);
                if (!words.length) return;
                const sy = [...ly.children].filter((c) => c.tagName === 'syllabic').pop();
                const syl = sy ? sy.textContent.trim() : '';
                setLyric(ev, v, words.join('‿') + (syl === 'begin' || syl === 'middle' ? '-' : ''));
              });
            }
            for (const sp of openSpans) if (sp.k === k && !sp.a) sp.a = { m, pos: start };
            lastAt[k] = { m, pos: start };
          }
          list.push({ pos: start, ev, dur, drop, split });
        }
      }
      const timeB = timeAt(score, m).length > 2 ? [time[0], time[1], timeAt(score, m)[2]] : time;
      // build each staff's bar, with rests in any gaps: each voice in its own lane; a note that
      // overlaps another of its voice (or of a fifth voice) goes to a lane where there is room
      const bt = barTicks(timeB);
      part.staves.forEach((st, k) => {
        const lanes = [[], [], [], []];
        const lenOf = (x) => Math.max(1, x.ev.full ? bt : x.dur);
        const clash = (li, a, b, notesOnly) => lanes[li].some((y) => (!notesOnly || !y.ev.rest) && a < y.pos + lenOf(y) && y.pos < b);
        const spill = [];
        const native = [perStaff[k], perStaffV[k][2], perStaffV[k][3], perStaffV[k][4]];
        native.forEach((l, li) => {
          for (const x of l.filter((x) => x.pos >= 0 && x.pos < bt && !x.drop).sort((a, b) => a.pos - b.pos)) {
            const a = x.pos, b = Math.min(bt, a + lenOf(x));
            if (!clash(li, a, b)) lanes[li].push(x); else if (x.ev.notes) spill.push(x);
          }
        });
        for (const l of Object.values(extraV[k])) for (const x of l) if (x.pos >= 0 && x.pos < bt && !x.drop && x.ev.notes) spill.push(x);
        for (const x of spill.sort((a, b) => a.pos - b.pos)) {
          const a = x.pos, b = Math.min(bt, a + lenOf(x));
          // (the same moment and length as a note already there: one chord)
          let host = null;
          for (const L of lanes) { host = L.find((y) => y.pos === a && y.ev.notes && lenOf(y) === lenOf(x)); if (host) break; }
          if (host) { for (const n of x.ev.notes) if (!host.ev.notes.some((h) => h.s === n.s && h.a === n.a)) host.ev.notes.push(n); continue; }
          const li = [0, 1, 2, 3].find((i) => !clash(i, a, b, true));
          if (li === undefined) continue;
          lanes[li] = lanes[li].filter((y) => !(y.ev.rest && a < y.pos + lenOf(y) && y.pos < b));
          lanes[li].push(x);
        }
        const build = (L) => {
          const evs = []; let p = 0;
          for (const x of L.sort((a, b) => a.pos - b.pos)) {
            // (a tick or two out, from rounding in the file: put right next to the note before)
            // (overlaps inside a voice were moved to other lanes above, so a note that starts before
            // the end of the one before is only rounding in the file)
            // (nothing shorter than a 128th can be written: a smaller gap is rounding)
            if (x.pos >= p + 15) evs.push(...gapRests(p, x.pos - p, timeB)); else x.pos = p;
            if (x.pos >= bt) continue;
            const len = x.ev.full ? bt : Math.min(x.dur, bt - x.pos);
            // (a note that runs past the end of the bar is cut at the barline)
            if (!x.ev.full && x.ev.notes && x.pos + M0.ticksOf(x.ev, timeB) > bt + 2) x.split = true;
            if (x.split && x.ev.notes) {
              // a length no written value has: tied notes that add up to it
              const pcs = M0.decompose(x.pos, len, timeB, false);
              if (pcs.reduce((s2, pc) => s2 + pc.ticks, 0) === len) {
                pcs.forEach((pc, i) => evs.push(i === 0 ? { ...x.ev, t: pc.t, dots: pc.dots, notes: x.ev.notes.map((n) => ({ ...n, tie: i < pcs.length - 1 ? true : n.tie })) }
                  : { id: newId(), t: pc.t, dots: pc.dots, notes: x.ev.notes.map((n) => ({ ...n, tie: i < pcs.length - 1 ? true : n.tie })) }));
                p = x.pos + len; continue;
              }
            }
            evs.push(x.ev); p = x.pos + (x.ev.full ? bt : M0.ticksOf(x.ev, timeB));
          }
          if (bt - p >= 15) evs.push(...gapRests(p, bt - p, timeB));
          if (!evs.length) return restBar(timeB);
          // (whatever the file held, the bar adds up exactly: rests at its end give way, or fill it)
          const out = tidyBar(evs, timeB);
          let sum = out.reduce((a, e) => a + M0.ticksOf(e, timeB), 0);
          while (sum > bt && out.length > 1 && out[out.length - 1].rest) sum -= M0.ticksOf(out.pop(), timeB);
          if (sum > bt) { const e = out[out.length - 1], room = bt - (sum - M0.ticksOf(e, timeB)); const v = room > 0 && (valueFor(room) || valueOf(room)); if (v) { e.t = v.t; e.dots = v.dots; if (v.tup) e.tup = v.tup; else delete e.tup; sum = bt - room + M0.ticksOf(e, timeB); } }
          if (sum < bt) out.push(...gapRests(sum, bt - sum, timeB));
          return out;
        };
        st.bars[m] = build(lanes[0]);
        for (const vn of [2, 3, 4]) {
          if (!lanes[vn - 1].length) continue;
          const key = 'v' + vn; st[key] = st[key] || []; st[key][m] = build(lanes[vn - 1]);
        }
      });
    }
    // ("Trumpet in C" with no transposition in the file: written as it sounds)
    if (!trSeen && inst.tr && (inst.tr.steps || inst.tr.semis) && /\bin (c|do|ut)\b/i.test(pname)) part.tr = { steps: 0, semis: 0 };
  });
  for (const p of score.parts) for (const st of p.staves) for (const key of ['v2', 'v3', 'v4']) if (st[key]) for (let m = 0; m < score.measures.length; m++) if (!st[key][m]) st[key][m] = restBar(timeAt(score, m));
  score.spans = (score.spans || []).filter((sp) => sp.a && sp.b);
  if (!score.measures[0].time) score.measures[0].time = [4, 4];
  if (score.measures[0].key === undefined) score.measures[0].key = 0;
  if (!score.measures[0].tempo) score.measures[0].tempo = { bpm: 96, beat: 4, text: '' };
  score.measures[score.measures.length - 1].bar = 'final';
  const n = score.parts.reduce((a, p) => a + p.staves.length, 0);
  score.layout.staffMm = n <= 2 ? 7 : n <= 4 ? 6.5 : n <= 8 ? 5.5 : 4.8;
  // an orchestra's strings are sections (a part called solo stays solo): Violin I and II, violas,
  // cellos and basses with winds and brass around them
  const fam = (id) => (INST[id] || {}).fam;
  const orch = score.parts.length >= 8 || (score.parts.some((p) => fam(p.inst) === 'brass') && score.parts.some((p) => fam(p.inst) === 'wind') && score.parts.some((p) => fam(p.inst) === 'str'));
  if (orch) for (const p of score.parts) {
    if (/solo/i.test(p.name || '')) continue;
    const nm = (p.name || '').toLowerCase();
    const to = p.inst === 'violin' ? (/\b(ii|2)\b/.test(nm) ? 'violin2' : 'violin1') : p.inst === 'viola' ? 'violas' : p.inst === 'cello' ? 'cellos' : p.inst === 'contrabass' ? 'contrabasses' : null;
    if (to && INST[to]) p.inst = to;
  }
  // chamber music: "Violin I" and "Violin II" of a string quartet are one player each, not sections
  // (only a plural name, violins, violini, violoncelli, keeps a section: a string orchestra)
  if (!orch) for (const p of score.parts) {
    const nm = (p.name || '').toLowerCase();
    if (/violins|violini|violons|violas|viole\b|altos|cellos|violoncelli|violoncelles|basses|bassi|kontrab|section|tutti/.test(nm)) continue;
    const to = p.inst === 'violin1' || p.inst === 'violin2' ? 'violin' : p.inst === 'violas' ? 'viola' : p.inst === 'cellos' ? 'cello' : p.inst === 'contrabasses' ? 'contrabass' : null;
    if (to && INST[to]) p.inst = to;
  }
  // slurs and hairpins were read as marks on notes: turn them into lines
  delete score._v2spans;
  // verses numbered 2 and 3 in the file (or by names) are the first and second lines of that part
  for (const p of score.parts) {
    const evs = []; for (const st of p.staves) for (const bars of [st.bars, ...[2, 3, 4].map((v) => st['v' + v]).filter(Boolean)]) for (const bar of bars) for (const ev of bar || []) if (ev.lyric || ev.lyricV) evs.push(ev);
    const used = new Set(); for (const ev of evs) for (let v = 1, n = versesOf(ev); v <= n; v++) if (lyricOf(ev, v)) used.add(v);
    const order = [...used].sort((a, b) => a - b);
    if (order.every((v, i) => v === i + 1)) continue;
    for (const ev of evs) { const ls = order.map((v) => lyricOf(ev, v)); delete ev.lyric; delete ev.lyricV; ls.forEach((l, i) => { if (l) setLyric(ev, i + 1, l); }); }
  }
  return migrateScore(score);
}
