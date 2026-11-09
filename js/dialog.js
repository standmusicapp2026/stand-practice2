// A small in-app question (the iPad app's web view does not show the browser's own dialogs).
// ask('Discard these pages?', { ok: 'Discard', danger: true }) -> Promise<boolean>
export function ask(text, { ok = 'OK', cancel = 'Cancel', danger = false, sub = '' } = {}) {
  return new Promise((resolve) => {
    const back = document.createElement('div'); back.className = 'ask-back';
    const box = document.createElement('div'); box.className = 'ask'; box.setAttribute('role', 'alertdialog');
    const h = document.createElement('p'); h.className = 'ask-title'; h.textContent = text; box.append(h);
    if (sub) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = sub; box.append(p); }
    const row = document.createElement('div'); row.className = 'ask-row';
    const no = document.createElement('button'); no.className = 'btn'; no.textContent = cancel;
    const yes = document.createElement('button'); yes.className = 'btn ' + (danger ? 'danger-fill' : 'primary'); yes.textContent = ok;
    row.append(no, yes); box.append(row); back.append(box); document.body.append(back);
    const done = (v) => { back.remove(); resolve(v); };
    no.addEventListener('click', () => done(false)); yes.addEventListener('click', () => done(true));
    back.addEventListener('click', (e) => { if (e.target === back) done(false); });
    setTimeout(() => yes.focus(), 30);
  });
}

// One of a list (a score, a part): choose('Which part?', [{ id, title, sub }], { sub }) -> Promise<id | null>
export function choose(text, items, { sub = '', cancel = 'Cancel' } = {}) {
  return new Promise((resolve) => {
    const back = document.createElement('div'); back.className = 'ask-back';
    const box = document.createElement('div'); box.className = 'ask choose'; box.setAttribute('role', 'dialog');
    const h = document.createElement('p'); h.className = 'ask-title'; h.textContent = text; box.append(h);
    if (sub) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = sub; box.append(p); }
    const list = document.createElement('div'); list.className = 'choose-list';
    const done = (v) => { back.remove(); resolve(v); };
    for (const it of items) {
      const b = document.createElement('button'); b.className = 'choose-item';
      const t = document.createElement('b'); t.textContent = it.title; t.setAttribute('translate', 'no'); b.append(t);
      if (it.sub) { const s2 = document.createElement('small'); s2.textContent = it.sub; s2.setAttribute('translate', 'no'); b.append(s2); }
      b.addEventListener('click', () => done(it.id));
      list.append(b);
    }
    box.append(list);
    const row = document.createElement('div'); row.className = 'ask-row';
    const no = document.createElement('button'); no.className = 'btn'; no.textContent = cancel;
    no.addEventListener('click', () => done(null));
    row.append(no); box.append(row); back.append(box); document.body.append(back);
    back.addEventListener('click', (e) => { if (e.target === back) done(null); });
  });
}
