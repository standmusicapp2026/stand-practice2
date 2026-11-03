// Linking an iPad and an iPhone (or two of either), once. Both open this screen; when they find
// each other one shows four numbers and the other types them. From then on the two know each
// other: they connect by themselves whenever they are near, and no other device can.
import { PAIR, pairMode, pairCode, pairWatch, pairList, pairForget, directPeers } from './link.js';
import { ask } from './dialog.js';

const PHONE_UA = () => /iPhone|iPod/.test(navigator.userAgent);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };

let open = null;
// resolves true when a device was linked, false when closed without
export function openPair() {
  if (!PAIR()) return Promise.resolve(false);
  if (open) return open;
  open = new Promise((resolve) => {
    const me = PHONE_UA() ? 'iPhone' : 'iPad', other = me === 'iPhone' ? 'iPad' : 'iPhone';
    const back = el('div', 'ask-back pair-back');
    const box = el('div', 'ask pair'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Link a device');
    const title = el('p', 'ask-title', 'Link your ' + other);
    const say = el('p', 'hint pair-say');
    const find = el('div', 'pair-find'); find.append(el('i'), el('span', '', 'Looking for it nearby…'));
    const code = el('div', 'pair-code num'); code.hidden = true;
    const input = el('input', 'pair-input num'); input.hidden = true;
    Object.assign(input, { inputMode: 'numeric', maxLength: 4, autocomplete: 'one-time-code', placeholder: '····' });
    input.setAttribute('pattern', '[0-9]*'); input.setAttribute('aria-label', 'The four numbers shown on the other device');
    const bad = el('p', 'hint pair-bad'); bad.hidden = true;
    const row = el('div', 'ask-row');
    const cancel = el('button', 'btn', 'Cancel'); const again = el('button', 'btn primary', 'Try again'); again.hidden = true;
    row.append(cancel, again);
    box.append(title, say, find, code, input, bad, row); back.append(box); document.body.append(back);

    const intro = () => {
      say.textContent = me === 'iPad'
        ? 'On your iPhone, open Stand and tap Connect to iPad (or Settings › Linked devices › Link). Keep the two near each other.'
        : 'On your iPad, open Stand, then Settings › Linked devices › Link an iPhone. Keep the two near each other.';
      find.hidden = false; code.hidden = true; input.hidden = true; bad.hidden = true; again.hidden = true;
    };
    intro();
    let done = false, linkedOk = false;
    const finish = (ok) => {
      if (done) return; done = true;
      off(); pairMode(false); back.remove(); open = null; resolve(ok);
    };
    const off = pairWatch((type, d) => {
      if (type === 'show') {
        find.hidden = true; input.hidden = true; code.hidden = false; code.textContent = String(d.code || '').split('').join(' ');
        say.textContent = 'Type these four numbers on the ' + (d.kind || other) + '.';
      } else if (type === 'ask') {
        find.hidden = true; code.hidden = true; input.hidden = false; input.value = ''; setTimeout(() => input.focus(), 50);
        say.textContent = 'Type the four numbers shown on the ' + (d.kind || other) + '.';
      } else if (type === 'bad') {
        bad.hidden = false;
        bad.textContent = d.left > 0 ? (d.here ? 'A wrong code was typed on the other device. ' : 'Not those numbers. ') + d.left + (d.left === 1 ? ' try left.' : ' tries left.') : 'Too many wrong codes. Try again.';
        if (!d.here) { input.value = ''; input.focus(); }
        if (d.left <= 0) { input.hidden = true; code.hidden = true; again.hidden = false; }
      } else if (type === 'done') {
        find.hidden = true; code.hidden = true; input.hidden = true; bad.hidden = true;
        title.textContent = 'Linked';
        say.textContent = 'Your ' + (d.kind || other) + ' and this ' + me + ' now find each other by themselves whenever they are near. No code again.';
        linkedOk = true;
        cancel.textContent = 'Done'; cancel.classList.add('primary'); again.hidden = true;
        setTimeout(() => finish(true), 4000);
      } else if (type === 'lost') {
        if (title.textContent === 'Linked') return;
        intro(); say.textContent = 'The other device went away. Keep both open on this screen, near each other.';
      } else if (type === 'timeout') {
        find.hidden = true; code.hidden = true; input.hidden = true; again.hidden = false;
        say.textContent = 'Not found. Is Stand open on both, on this screen, with Wi-Fi and Bluetooth on?';
      }
    });
    input.addEventListener('input', () => {
      const v = input.value.replace(/\D/g, '').slice(0, 4); input.value = v;
      if (v.length === 4) { bad.hidden = true; pairCode(v); }
    });
    cancel.addEventListener('click', () => finish(linkedOk));
    again.addEventListener('click', () => { intro(); pairMode(false); setTimeout(() => pairMode(true), 300); });
    pairMode(true);
  });
  return open;
}

// Settings › Linked devices: the list, each with Forget, and Link
export async function drawLinked(card) {
  if (!card) return;
  card.hidden = !PAIR();
  if (!PAIR()) return;
  const list = await pairList();
  const ul = card.querySelector('.pair-list'); ul.textContent = '';
  const fmt = (t) => new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  for (const x of list) {
    const li = el('li');
    // (the two no longer hold the same key — one was forgotten, or reset: a new code puts it right)
    const name = el('span', x.stale ? 'pair-stale' : '', x.kind + (x.stale ? ' · link again with a code' : ' · linked ' + fmt(x.at)));
    const forget = el('button', 'btn small ghost', 'Forget');
    forget.addEventListener('click', async () => {
      if (!await ask('Forget this ' + x.kind + '?', { ok: 'Forget', danger: true, sub: 'The two will no longer connect until you link them again with a code.' })) return;
      pairForget(x.d); setTimeout(() => drawLinked(card), 400);
    });
    li.append(name, forget); ul.append(li);
  }
  const none = card.querySelector('.pair-none'); if (none) none.hidden = list.length > 0;
}
export const linkedCount = async () => (PAIR() ? (await pairList()).length : 0);
export { directPeers };
