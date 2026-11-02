"""Builds the progress page from progress.json -> /home/claude/progress/index.html, copying shots alongside."""
import json, shutil, os, html
P = '/home/claude/progress'
os.makedirs(P + '/shots', exist_ok=True)
data = json.load(open('/home/claude/tools/progress.json'))
items = []
for e in reversed(data['entries']):
    imgs = ''
    for s in e.get('shots', []):
        src = f'/home/claude/shots/{s}.png'
        if os.path.exists(src):
            shutil.copy(src, f'{P}/shots/{s}.png')
            imgs += f'<figure><img src="shots/{s}.png" alt="{html.escape(e["title"])}" loading="lazy"></figure>'
    state = e.get('state', 'done')
    items.append(f'''<article class="entry {state}">
  <div class="meta"><span class="chip {state}">{ {"done":"Done","wip":"Working on it","next":"Up next"}[state] }</span><time>{html.escape(e.get("time",""))}</time></div>
  <h2>{html.escape(e["title"])}</h2>
  <p>{html.escape(e.get("text",""))}</p>
  <div class="shots">{imgs}</div>
</article>''')
plan = ''.join(f'<li class="{s}"><i></i>{html.escape(t)}</li>' for t, s in data['plan'])
page = f'''<title>Stand Build Log</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: a single reading column, plan checklist on top, newest progress first with screenshots. */
:root {{
  --bg: #F3F4F7; --surface: #FFFFFF; --ink: #121522; --muted: #61687B; --line: rgba(18,21,34,.10);
  --accent: #1F3A8F; --good: #1E8E55; --warn: #C27A00;
  --serif: ui-serif, "New York", "Iowan Old Style", Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0B0E16; --surface:#161B29; --ink:#E9ECF4; --muted:#959DB2; --line:rgba(255,255,255,.09); --accent:#A9BCFF; --good:#3CC47F; --warn:#F0B23A; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg:#0B0E16; --surface:#161B29; --ink:#E9ECF4; --muted:#959DB2; --line:rgba(255,255,255,.09); --accent:#A9BCFF; --good:#3CC47F; --warn:#F0B23A; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
.wrap {{ max-width: 980px; margin: 0 auto; padding-block: 32px 64px; display: flex; flex-direction: column; gap: 28px; }}
header h1 {{ font: 600 40px/1 var(--serif); color: var(--accent); margin: 0; }}
header p {{ color: var(--muted); margin: 8px 0 0; max-width: 65ch; }}
.plan {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 16px 20px; }}
.plan h3 {{ margin: 0 0 10px; font-size: 12px; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }}
.plan ul {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 18px; }}
.plan li {{ display: flex; gap: 10px; align-items: center; font-size: 14px; }}
.plan li i {{ width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--muted); flex: none; }}
.plan li.done i {{ background: var(--good); border-color: var(--good); }}
.plan li.wip i {{ border-color: var(--warn); background: color-mix(in srgb, var(--warn) 35%, transparent); }}
.entry {{ background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 18px 20px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }}
.entry h2 {{ font: 600 22px/1.2 var(--serif); margin: 0; text-wrap: balance; }}
.entry p {{ margin: 0; color: var(--muted); max-width: 70ch; }}
.meta {{ display: flex; gap: 10px; align-items: center; font-size: 13px; color: var(--muted); }}
.chip {{ font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 20px; }}
.chip.done {{ background: color-mix(in srgb, var(--good) 16%, transparent); color: var(--good); }}
.chip.wip {{ background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }}
.chip.next {{ background: var(--line); color: var(--muted); }}
.shots {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 6px; }}
.shots:empty {{ display: none; }}
figure {{ margin: 0; }}
figure img {{ width: 100%; border-radius: 10px; border: 1px solid var(--line); display: block; }}
</style>
<div class="wrap">
<header><h1>Stand</h1><p>Stand 2.10: the fixes and improvements from your list of October 22, newest at the top. Screenshots are taken from the app running in a browser at iPad size.</p></header>
<section class="plan"><h3>Plan</h3><ul>{plan}</ul></section>
{''.join(items)}
</div>'''
open(P + '/index.html', 'w').write(page)
print('built', len(data['entries']))
