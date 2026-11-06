// Tuning systems, note names and instruments shared by the tuner, drone and scale player.
export const NOTE_NAMES = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B'];

// Frequency ratios above the key note for each of the 12 semitones.
export const SYSTEMS = {
  equal: { label: 'Equal', long: 'Equal temperament', ratios: null },
  just: { label: 'Just', long: 'Just (pure thirds and fifths)', ratios: [1, 16 / 15, 9 / 8, 6 / 5, 5 / 4, 4 / 3, 45 / 32, 3 / 2, 8 / 5, 5 / 3, 9 / 5, 15 / 8] },
  pyth: { label: 'Pythagorean', long: 'Pythagorean (pure fifths, high leading notes)', ratios: [1, 256 / 243, 9 / 8, 32 / 27, 81 / 64, 4 / 3, 729 / 512, 3 / 2, 128 / 81, 27 / 16, 16 / 9, 243 / 128] },
};

// Cents that a note sits away from equal temperament in the chosen system and key.
export function centsOffset(pc, key, system) {
  const sys = SYSTEMS[system];
  if (!sys || !sys.ratios) return 0;
  const d = (((pc - key) % 12) + 12) % 12;
  return 1200 * Math.log2(sys.ratios[d]) - 100 * d;
}

export const etFreq = (midi, ref) => ref * Math.pow(2, (midi - 69) / 12);
export const tunedFreq = (midi, ref, key, system) => etFreq(midi, ref) * Math.pow(2, centsOffset(((midi % 12) + 12) % 12, key, system) / 1200);
export const midiName = (m) => NOTE_NAMES[((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);

// One of each kind of instrument, in score order by family (a tuba is "Tuba", every drum is
// "Percussion"). The first eleven names are the ones saved in older settings and stay as they were.
// strings: open strings (MIDI); fifths: tuned in fifths (pure-fifths tuning offered);
// range: the notes it plays (sounding); clef: its own clef; tr: it sounds other than written.
const G = (group, label, words, range, more = {}) => ({ group, label, words, range, strings: null, ...more });
export const INSTRUMENT_GROUPS = ['Strings', 'Woodwinds', 'Brass', 'Keyboards', 'Plucked', 'Percussion', 'Voice', ''];
export const INSTRUMENTS = {
  cello: G('Strings', 'Cello', ['cello', 'violoncell', 'violoncelle', 'vc.', 'vlc', 'violoncello'], [36, 84], { strings: [36, 43, 50, 57], fifths: true, clef: 'bass' }),
  violin: G('Strings', 'Violin', ['violin', 'violino', 'violon ', 'violine', 'vn.'], [55, 100], { strings: [55, 62, 69, 76], fifths: true, clef: 'treble' }),
  viola: G('Strings', 'Viola', ['viola', 'alto', 'bratsche'], [48, 91], { strings: [48, 55, 62, 69], fifths: true, clef: 'alto' }),
  bass: G('Strings', 'Double bass', ['double bass', 'contrabass', 'contrabbasso', 'kontrabass', 'bass'], [28, 67], { strings: [28, 33, 38, 43], fifths: false, clef: 'bass' }),
  guitar: G('Plucked', 'Guitar', ['guitar', 'chitarra', 'guitare', 'gitarre'], [40, 88], { strings: [40, 45, 50, 55, 59, 64], fifths: false, clef: 'tab' }),
  flute: G('Woodwinds', 'Flute', ['flute', 'flauto', 'flöte', 'flote', 'traverso'], [60, 98]),
  clarinet: G('Woodwinds', 'Clarinet', ['clarinet', 'clarinetto', 'klarinette', 'clarinette'], [50, 94], { tr: true }),
  oboe: G('Woodwinds', 'Oboe', ['oboe', 'hautbois'], [58, 91]),
  piano: G('Keyboards', 'Piano', ['piano', 'pianoforte', 'klavier', 'keyboard'], [21, 108], { clef: 'piano', keys: true }),
  voice: G('Voice', 'Voice', ['voice', 'soprano', 'alto', 'tenor', 'baritone', 'vocal', 'gesang', 'canto'], [40, 84]),
  // (more of each family; "Other" stays last)
  gamba: G('Strings', 'Viola da gamba', ['viola da gamba', 'gamba', 'viol '], [38, 81], { strings: [38, 43, 48, 52, 57, 62], fifths: false, clef: 'alto' }),
  piccolo: G('Woodwinds', 'Piccolo', ['piccolo', 'ottavino'], [74, 108]),
  recorder: G('Woodwinds', 'Recorder', ['recorder', 'flauto dolce', 'blockflöte', 'flûte à bec'], [60, 98]),
  englishhorn: G('Woodwinds', 'English horn', ['english horn', 'cor anglais', 'corno inglese', 'englischhorn'], [52, 84], { tr: true }),
  bassoon: G('Woodwinds', 'Bassoon', ['bassoon', 'fagott', 'fagotto', 'basson'], [34, 75], { clef: 'bass' }),
  saxophone: G('Woodwinds', 'Saxophone', ['saxophone', 'sax', 'saxofon'], [44, 88], { tr: true }),
  horn: G('Brass', 'Horn', ['horn', 'corno', 'cor ', 'waldhorn'], [34, 77], { tr: true }),
  trumpet: G('Brass', 'Trumpet', ['trumpet', 'tromba', 'trompete', 'trompette', 'cornet'], [52, 84], { tr: true }),
  trombone: G('Brass', 'Trombone', ['trombone', 'posaune'], [34, 72], { clef: 'bass' }),
  euphonium: G('Brass', 'Euphonium', ['euphonium', 'baritone horn'], [34, 70], { clef: 'bass' }),
  tuba: G('Brass', 'Tuba', ['tuba'], [26, 65], { clef: 'bass' }),
  organ: G('Keyboards', 'Organ', ['organ', 'orgel', 'organo', 'orgue'], [24, 96], { clef: 'piano', keys: true }),
  harpsichord: G('Keyboards', 'Harpsichord', ['harpsichord', 'cembalo', 'clavecin'], [29, 89], { clef: 'piano', keys: true }),
  accordion: G('Keyboards', 'Accordion', ['accordion', 'akkordeon', 'fisarmonica', 'bandoneon'], [41, 93], { clef: 'piano', keys: true }),
  harp: G('Plucked', 'Harp', ['harp', 'arpa', 'harfe', 'harpe'], [24, 103], { clef: 'piano', keys: true }),
  bassguitar: G('Plucked', 'Bass guitar', ['bass guitar', 'electric bass', 'e-bass'], [28, 67], { strings: [28, 33, 38, 43], fifths: false, clef: 'bass' }),
  mandolin: G('Plucked', 'Mandolin', ['mandolin', 'mandolino', 'mandoline'], [55, 88], { strings: [55, 62, 69, 76], fifths: true, clef: 'treble' }),
  ukulele: G('Plucked', 'Ukulele', ['ukulele'], [60, 81], { strings: [67, 60, 64, 69], fifths: false, clef: 'treble' }),
  lute: G('Plucked', 'Lute', ['lute', 'liuto', 'laute', 'theorbo'], [40, 81], { clef: 'tab' }),
  percussion: G('Percussion', 'Percussion', ['percussion', 'timpani', 'marimba', 'xylophone', 'vibraphone', 'drum', 'schlagzeug'], [45, 96], { keys: true }),
  other: G('', 'Other', [], null),
};


// Open-string targets. Bowed strings can be tuned in pure 3:2 fifths from the A string.
export function stringTargets(inst, ref, pureFifths) {
  const def = INSTRUMENTS[inst];
  if (!def || !def.strings) return [];
  const s = def.strings;
  const aIdx = s.findIndex((m) => m % 12 === 9);
  return s.map((m, i) => {
    let f = etFreq(m, ref);
    if (pureFifths && def.fifths && aIdx >= 0) f = etFreq(s[aIdx], ref) * Math.pow(1.5, i - aIdx);
    return { midi: m, name: NOTE_NAMES[m % 12], label: midiName(m), freq: f };
  });
}
