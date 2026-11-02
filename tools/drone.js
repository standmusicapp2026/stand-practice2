document.querySelector('.tile[data-tile="drone"]').click();
---
WAIT 600
---
document.querySelector('#droneModeSeg [data-mode="list"]').click();
---
document.querySelector('#droneListAdd').click();
---
for (const k of [2, 7, 9]) document.querySelectorAll('#droneNotes button')[k].click(); return [...document.querySelectorAll('#droneChips button')].map(b=>b.textContent);
---
SHOT drone_adding
---
document.querySelector('#droneListAdd').click(); [...document.querySelectorAll('#droneSoundSeg button')].find(b=>b.dataset.sound==='bow').click(); document.querySelector('#droneToggle').click();
---
WAIT 1200
---
const { getCtx } = await import('/js/audio.js'); return [getCtx().state, document.querySelector('#dronePillNote').textContent, [...document.querySelectorAll('#droneSoundSeg button')].map(b=>b.textContent)];
---
SHOT drone_bow
