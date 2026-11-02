# Winks from the iPad's face tracking, simulated: levels at 60 a second and the iPad's own wink events
import asyncio
from playwright.async_api import async_playwright
SIM = """async ([restL, restR, eye, peak, other, native, ms]) => {
  const sleep = (t) => new Promise((r) => setTimeout(r, t));
  document.querySelector('#winkLast').textContent = '';
  // (as the iPad's camera sends them: mirrored, its left is your right)
  const send = (l, r) => window.standFaceEvent({ type: 'levels', l: r, r: l });
  for (let i = 0; i < 150; i++) { send(restL + Math.random() * 0.03, restR + Math.random() * 0.03); await sleep(16); }
  // the eye shuts quickly, stays shut, opens
  const steps = Math.round(ms / 16);
  for (let i = 0; i < steps; i++) {
    const k = Math.min(1, i / 4);
    const shut = (eye === 'left' ? restL : restR) + (peak - (eye === 'left' ? restL : restR)) * k;
    const oth = (eye === 'left' ? restR : restL) + (other - (eye === 'left' ? restR : restL)) * k;
    if (eye === 'left') send(shut, oth); else send(oth, shut);
    if (i === 6 && native) window.standFaceEvent({ type: 'wink', eye: eye === 'left' ? 'right' : 'left' });
    await sleep(16);
  }
  for (let i = 0; i < 40; i++) { send(restL, restR); await sleep(16); }
  return document.querySelector('#winkLast').textContent || '(nothing)';
}"""
CASES = [
  ('front, right wink, iPad saw it', 0.05, 0.05, 'right', 0.85, 0.08, True, 250),
  ('front, left wink, iPad saw it', 0.06, 0.05, 'left', 0.8, 0.1, True, 250),
  ('front, soft right wink (0.6), iPad saw it', 0.05, 0.05, 'right', 0.6, 0.12, True, 220),
  ('aside, right wink, iPad missed it', 0.05, 0.38, 'right', 0.9, 0.08, False, 260),
  ('aside, left (near) wink, iPad saw it', 0.06, 0.4, 'left', 0.85, 0.42, True, 260),
  ('both eyes closed, iPad called it a wink', 0.05, 0.05, 'right', 0.85, 0.82, True, 400),
  ('aside, both closed', 0.05, 0.38, 'right', 0.9, 0.85, True, 400),
  ('front, blink no event', 0.05, 0.05, 'right', 0.85, 0.85, False, 200),
]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); }")
        await pg.evaluate("() => { const b = document.querySelector('#winkTest'); b && b.click(); }")
        for c in CASES:
            r = await pg.evaluate(SIM, list(c[1:]))
            print(f'{c[0]:45s} -> {r}')
            await pg.wait_for_timeout(1000)
        await b.close()
asyncio.run(main())
