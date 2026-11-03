# Linking with a code, once: an iPad, its iPhone and a stranger's iPhone, each its own app. The native
# link (StandNativeExtras.swift) is played here step by step as it is written there: who may connect,
# the "hi" with a random number, the proof with the key, the code, the key handed over. Checked:
#  - nothing passes before linking (the stranger, and the iPhone before its code)
#  - a wrong code is refused, the right one links; the list in Settings shows it
#  - both apps started again: they find each other with no code, and the practice comes
#  - the stranger, never linked, never connects nor gets anything, even while the two link
#  - Forget: the two no longer connect
import asyncio, os, json, uuid, hmac, hashlib, base64, random
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
PORT = os.environ.get('PORT', '8765')
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
def mac(key, msg): return base64.b64encode(hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()).decode()

class Dev:
    def __init__(self, name, kind):
        self.name, self.kind = name, kind
        self.id = str(uuid.uuid4()).upper()
        self.linked = {}            # UserDefaults "standLinked": survives a restart
        self.reset()
    def reset(self):                # the app started (again)
        self.pg = None; self.on = False; self.pairMode = False
        self.verified = set(); self.nonce = {}; self.peerDev = {}; self.peerKind = {}; self.pairing = None
    def allowed(self, d): return bool(d) and d != self.id and (self.pairMode or d in self.linked)

class Net:
    def __init__(self, devs): self.devs = devs; self.conn = set(); self.log = []
    def key(self, a, b): return frozenset((a.name, b.name))
    async def js(self, dev, src):
        if dev.pg:
            try: await dev.pg.evaluate(src)
            except Exception as e: self.log.append('js error ' + str(e)[:80])
    async def event(self, dev, t, data): await self.js(dev, f"window.standPairEvent && window.standPairEvent({json.dumps(t)}, {json.dumps(data)})")
    async def state(self, dev):
        ps = [o for o in self.devs if self.key(dev, o) in self.conn and o.name in dev.verified]
        await self.js(dev, f"window.standPeerState && window.standPeerState({len(ps)}, {json.dumps(['Stand ' + o.kind for o in ps])})")
    # who connects: both on, both allow each other (the inviter invites only those it allows; the
    # invited accepts only those it allows)
    async def settle(self):
        for a in self.devs:
            for b in self.devs:
                if a.name >= b.name or not (a.on and b.on): continue
                k = self.key(a, b)
                if k not in self.conn and a.allowed(b.id) and b.allowed(a.id):
                    self.conn.add(k); a.peerDev[b.name] = b.id; b.peerDev[a.name] = a.id
                    self.log.append(f'connect {a.name}-{b.name}')
                    await self.greet(a, b); await self.greet(b, a)
    async def drop(self, a, b):
        k = self.key(a, b)
        if k not in self.conn: return
        self.conn.discard(k); self.log.append(f'drop {a.name}-{b.name}')
        for x, y in ((a, b), (b, a)):
            x.verified.discard(y.name); x.nonce.pop(y.name, None)
            if x.pairing and x.pairing['peer'] == y.name: x.pairing = None; await self.event(x, 'lost', {})
            await self.state(x)
    async def auth(self, frm, to, m):
        if self.key(frm, to) in self.conn: await self.handle(to, frm, m)
    async def greet(self, me, peer):
        n = str(uuid.uuid4()); me.nonce[peer.name] = n
        d = me.peerDev.get(peer.name)
        await self.auth(me, peer, {'op': 'hi', 'd': me.id, 'k': me.kind, 'n': n, 'pm': me.pairMode, 'tr': d in me.linked if d else False})
    async def handle(self, me, peer, m):
        op = m['op']
        if op == 'hi':
            d, n = m['d'], m['n']
            me.peerDev[peer.name] = d; me.peerKind[peer.name] = m['k']
            if me.pairMode and m['pm']:
                if me.pairing:
                    if me.pairing['peer'] != peer.name: await self.drop(me, peer)
                    else: me.pairing['theirNonce'] = n
                    return
                show = (me.kind == 'iPad' and m['k'] != 'iPad') or (me.kind == m['k'] and me.id < d)
                code = '%04d' % random.randint(0, 9999)
                me.pairing = {'peer': peer.name, 'shower': show, 'code': code, 'theirNonce': n, 'tries': 0, 'typed': None, 'pendingKey': None}
                await self.event(me, 'show' if show else 'ask', {'code': code, 'kind': m['k']} if show else {'kind': m['k']})
            elif d in me.linked and m['tr']:
                await self.auth(me, peer, {'op': 'proof', 'm': mac(me.linked[d]['key'], n + '|' + me.id)})
            elif m['tr']:
                await self.auth(me, peer, {'op': 'forgot'}); await self.drop(me, peer)
            elif not me.pairMode:
                await self.drop(me, peer)
        elif op == 'proof':
            d = me.peerDev.get(peer.name)
            if d in me.linked and m['m'] == mac(me.linked[d]['key'], me.nonce[peer.name] + '|' + d):
                me.verified.add(peer.name); me.linked[d]['stale'] = False; await self.state(me)
            else:
                if d in me.linked: me.linked[d]['stale'] = True
                await self.drop(me, peer)
        elif op == 'pc':
            p = me.pairing
            if not p or p['peer'] != peer.name or not p['shower'] or p['pendingKey']: return
            if p['tries'] >= 5: await self.drop(me, peer); return
            if m['m'] == mac(p['code'], me.nonce[peer.name] + '|pair'):
                key = base64.b64encode(os.urandom(32)).decode(); p['pendingKey'] = key
                await self.auth(me, peer, {'op': 'key', 'k': key, 'm': mac(p['code'], p['theirNonce'] + '|show')})
            else:
                p['tries'] += 1; left = 5 - p['tries']
                await self.auth(me, peer, {'op': 'bad', 'left': left})
                await self.event(me, 'bad', {'left': left, 'here': True})
                if left <= 0: await self.drop(me, peer)
        elif op == 'key':
            p = me.pairing
            if not p or p['peer'] != peer.name or p['shower'] or not p['typed']: return
            if m.get('m') != mac(p['typed'], me.nonce[peer.name] + '|show'): self.log.append(f"key without proof refused typed={p['typed']} shower={getattr(peer, 'pairing', None) and peer.pairing.get('code')}"); await self.drop(me, peer); return
            me.linked[me.peerDev[peer.name]] = {'key': m['k'], 'kind': me.peerKind[peer.name], 'at': 1.7e12}
            await self.auth(me, peer, {'op': 'ok', 'm': mac(m['k'], p['theirNonce'] + '|ok')})
            me.pairing = None; me.verified.add(peer.name)
            await self.event(me, 'done', {'kind': me.peerKind[peer.name]}); await self.list(me); await self.state(me)
        elif op == 'ok':
            p = me.pairing
            if not p or p['peer'] != peer.name or not p['shower'] or not p['pendingKey']: return
            if m['m'] != mac(p['pendingKey'], me.nonce[peer.name] + '|ok'): return
            me.linked[me.peerDev[peer.name]] = {'key': p['pendingKey'], 'kind': me.peerKind[peer.name], 'at': 1.7e12}
            me.pairing = None; me.verified.add(peer.name)
            await self.event(me, 'done', {'kind': me.peerKind[peer.name]}); await self.list(me); await self.state(me)
        elif op == 'bad':
            await self.event(me, 'bad', {'left': m['left']})
        elif op == 'forgot':
            d = me.peerDev.get(peer.name)
            if d in me.linked: me.linked[d]['stale'] = True
            await self.list(me); await self.drop(me, peer)
    async def list(self, me):
        l = [{'d': d, 'kind': v['kind'], 'at': v['at'], 'stale': bool(v.get('stale'))} for d, v in me.linked.items()]
        await self.event(me, 'list', {'list': l, 'me': me.kind})
    # messages from a page
    async def from_page(self, me, msg):
        op = msg.get('op')
        if op == 'start':
            me.on = True; await self.settle()
        elif op == 'send':
            for o in self.devs:
                if self.key(me, o) in self.conn and o.name in me.verified and me.name in o.verified:
                    s = msg['data']
                    await self.js(o, f"window.standPeerMessage && window.standPeerMessage({json.dumps(s)})")
                elif self.key(me, o) in self.conn and o.name in me.verified:
                    self.log.append('dropped at ' + o.name)
        elif op == 'pairMode':
            me.pairMode = bool(msg.get('on'))
            if me.pairMode: me.codes = 0
            if me.pairMode: await self.settle()
            elif me.pairing:
                p = me.pairing; me.pairing = None
                if p['peer'] not in me.verified:
                    await self.drop(me, next(o for o in self.devs if o.name == p['peer']))
        elif op == 'pairCode':
            p = me.pairing
            if p and not p['shower']:
                p['typed'] = msg['code']
                peer = next(o for o in self.devs if o.name == p['peer'])
                await self.auth(me, peer, {'op': 'pc', 'm': mac(msg['code'], p['theirNonce'] + '|pair')})
        elif op == 'pairList':
            await self.list(me)
        elif op == 'pairForget':
            gone = [msg['d']] if msg.get('d') else list(me.linked)
            for g in gone: me.linked.pop(g, None)
            for o in self.devs:
                if o.id in gone: await self.drop(me, o)
            await self.list(me); await self.state(me)

IPAD_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)'
IPHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
BRIDGE = r"""
(() => {
  window.__noTour = true;
  window.standCaps = { peer: 4 };
  const sink = { postMessage() {} };
  const peer = { postMessage(m) { window.__peerOut(JSON.stringify(m)); } };
  window.webkit = { messageHandlers: new Proxy({ standPeer: peer }, { get: (t, k) => (k in t ? t[k] : (k === 'standDiag' ? sink : undefined)) }) };
})();
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad, phone, stranger = Dev('ipad', 'iPad'), Dev('phone', 'iPhone'), Dev('stranger', 'iPhone')
        net = Net([ipad, phone, stranger])
        errs = []
        async def boot(dev):
            dev.reset()
            ua = IPAD_UA if dev.kind == 'iPad' else IPHONE_UA
            vp = {'width': 1180, 'height': 820} if dev.kind == 'iPad' else {'width': 390, 'height': 844}
            if not hasattr(dev, 'ctx'):
                dev.ctx = await b.new_context(viewport=vp, user_agent=ua, has_touch=True, is_mobile=dev.kind != 'iPad')
                await dev.ctx.expose_binding('__peerOut', lambda src, s, d=dev: asyncio.ensure_future(net.from_page(d, json.loads(s))))
                await dev.ctx.add_init_script(BRIDGE)
            pg = await dev.ctx.new_page(); dev.pg = pg
            pg.on('pageerror', lambda e, n=dev.name: errs.append(n + ': ' + str(e)))
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(600)
            # the link starts as the app does (the practice host on the iPad, the asking on the iPhone)
            await pg.evaluate("async () => { const L = await import('/js/link.js'); await L.pairList(); }")
            await pg.wait_for_timeout(300)
        async def restart(dev):
            if dev.pg: await dev.pg.close()
            dev.on = False
            for o in net.devs: await net.drop(dev, o) if net.key(dev, o) in net.conn else None
            await boot(dev)
        for d in (ipad, phone, stranger): await boot(d)
        await ipad.pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await ipad.pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await ipad.pg.wait_for_timeout(3500)   # (the practice host starts 3 s in)
        peers = lambda d: d.pg.evaluate("async () => (await import('/js/link.js')).directPeers()")
        ok(not net.conn and await peers(ipad) == 0 and await peers(phone) == 0, 'before linking: no device connects to any other')
        # the iPhone asks for the practice: not linked, so the linking screen opens
        await phone.pg.evaluate("() => { const c = document.querySelector('#ipadCard'); c.classList.remove('waiting'); document.querySelector('#icEmpty').hidden = false; document.querySelector('#icConnect').click(); }")
        await phone.pg.wait_for_timeout(500)
        ok(await phone.pg.evaluate("() => !!document.querySelector('.pair') && document.querySelector('.pair .pair-find').offsetParent !== null"), 'iPhone: Connect to iPad opens the linking screen, looking')
        ok(not net.conn, 'only one side on the linking screen: still nothing connects')
        # the iPad: Settings › Linked devices › Link an iPhone
        await ipad.pg.evaluate("() => document.querySelector('[data-panel=app]').click()"); await ipad.pg.wait_for_timeout(600)
        card = await ipad.pg.evaluate("() => [!document.querySelector('#pairCard').hidden, document.querySelector('#pairNew').textContent.trim(), document.querySelector('#iphoneCodeRow').hidden]")
        print('card', card); ok(card[0] and card[1] == 'Link an iPhone' and card[2], 'iPad Settings: Linked devices with Link an iPhone (the old six-digit code row hidden)')
        await ipad.pg.evaluate("() => document.querySelector('#pairNew').click()"); await ipad.pg.wait_for_timeout(800)
        code = await ipad.pg.evaluate("() => document.querySelector('.pair .pair-code').textContent.replace(/\\s/g, '')")
        asks = await phone.pg.evaluate("() => !document.querySelector('.pair .pair-input').hidden")
        ok(len(code) == 4 and code.isdigit() and asks, f'the iPad shows four numbers ({code}), the iPhone asks for them')
        ok(net.key(ipad, stranger) not in net.conn and net.key(phone, stranger) not in net.conn, 'the stranger, not on the linking screen, is not connected')
        # nothing passes while not proved
        await ipad.pg.evaluate("async () => { const L = await import('/js/link.js'); const b = new L.DirectBox('x-test', () => {}); b.open(); b.send('y', 'T', {}); }")
        await ipad.pg.wait_for_timeout(200)
        ok(await peers(phone) == 0 and await peers(ipad) == 0, 'connected for linking, but neither counts the other as linked yet')
        wrong = '0000' if code != '0000' else '1111'
        await phone.pg.fill('.pair .pair-input', wrong); await phone.pg.wait_for_timeout(500)
        badt = await phone.pg.evaluate("() => document.querySelector('.pair .pair-bad').textContent")
        ok('4 tries left' in badt and not ipad.linked, 'a wrong code is refused: ' + badt)
        await phone.pg.fill('.pair .pair-input', code); await phone.pg.wait_for_timeout(800)
        t1 = await ipad.pg.evaluate("() => document.querySelector('.pair .ask-title')?.textContent")
        t2 = await phone.pg.evaluate("() => document.querySelector('.pair .ask-title')?.textContent")
        ok(t1 == 'Linked' and t2 == 'Linked' and phone.id in ipad.linked and ipad.id in phone.linked and ipad.linked[phone.id]['key'] == phone.linked[ipad.id]['key'], 'the right code links both, with the same key')
        await ipad.pg.wait_for_timeout(4500)
        ok(await ipad.pg.evaluate("() => !document.querySelector('.pair')"), 'the linking screen closes by itself')
        ok(await peers(ipad) == 1 and await peers(phone) == 1, 'both count the other as linked')
        lst = await ipad.pg.evaluate("() => [...document.querySelectorAll('#pairCard .pair-list li')].map(li => li.textContent)")
        ok(len(lst) == 1 and lst[0].startswith('iPhone · linked'), 'iPad Settings lists the iPhone: ' + str(lst))
        ok(not ipad.pairMode and not phone.pairMode, 'linking mode is off again on both')
        # the practice comes to the iPhone (Connect to iPad goes on to ask)
        await phone.pg.wait_for_timeout(6000)
        got = await phone.pg.evaluate("async () => { const S = await import('/js/sync.js'); try { const d = await S.fetchPractice(); return !!(d && d.v === 1); } catch (e) { return 'err ' + e.message; } }")
        ok(got is True, 'the iPhone gets the practice from the linked iPad: ' + str(got))
        # the stranger asks: never answered
        st = await stranger.pg.evaluate("async () => { const S = await import('/js/sync.js'); try { await S.fetchPractice(); return 'got it'; } catch (e) { return 'refused ' + e.message; } }")
        ok(st.startswith('refused') and net.key(ipad, stranger) not in net.conn, 'the stranger asks for the practice: nothing (' + st + ')')
        # both apps started again: no code, they find each other, the practice comes
        await restart(ipad); await restart(phone)
        await ipad.pg.wait_for_timeout(3500)
        await phone.pg.wait_for_timeout(1500)
        ok(await peers(ipad) == 1 and await peers(phone) == 1 and not await phone.pg.evaluate("() => !!document.querySelector('.pair')"), 'started again: linked by themselves, no code')
        got = await phone.pg.evaluate("async () => { const S = await import('/js/sync.js'); try { const d = await S.fetchPractice(); return !!(d && d.v === 1); } catch (e) { return 'err ' + e.message; } }")
        ok(got is True, 'after starting again the practice comes: ' + str(got))
        # the stranger opens the linking screen alone: the iPad is not on it, so nothing
        await stranger.pg.evaluate("async () => { (await import('/js/pair.js')).openPair(); }"); await stranger.pg.wait_for_timeout(800)
        ok(net.key(ipad, stranger) not in net.conn and net.key(phone, stranger) not in net.conn, 'the stranger on the linking screen alone: still not connected')
        await stranger.pg.evaluate("() => document.querySelector('.pair .btn').click()")
        # a forged proof (the right device id, the wrong key) is refused
        fake = Dev('fake', 'iPhone'); fake.id = phone.id; fake.linked = {ipad.id: {'key': 'not the key', 'kind': 'iPad', 'at': 0}}; fake.on = True
        net.devs.append(fake)
        await phone.pg.evaluate("() => 0")
        net.conn.add(net.key(ipad, fake)); ipad.peerDev['fake'] = phone.id; fake.peerDev['ipad'] = ipad.id
        await net.greet(ipad, fake); await net.greet(fake, ipad)
        ok('fake' not in ipad.verified and net.key(ipad, fake) not in net.conn, 'a device claiming to be the iPhone without its key is refused')
        net.devs.remove(fake)
        # a device that says "forget me" without proving anything: nothing is deleted
        fake2 = Dev('fake2', 'iPhone'); fake2.id = phone.id; fake2.on = True; net.devs.append(fake2)
        net.conn.add(net.key(ipad, fake2)); ipad.peerDev['fake2'] = phone.id
        await net.auth(fake2, ipad, {'op': 'forgot'})
        ok(phone.id in ipad.linked, 'a "forget me" from a device that proved nothing deletes nothing')
        ipad.linked[phone.id]['stale'] = False; net.devs.remove(fake2); net.conn.discard(net.key(ipad, fake2))
        # a device on the linking screen that hands over a key without knowing the code: refused
        evil = Dev('evil', 'iPad'); evil.id = '00000000-EVIL'; evil.on = True; evil.pairMode = True; net.devs.append(evil)
        await stranger.pg.evaluate("async () => { (await import('/js/pair.js')).openPair(); }"); await stranger.pg.wait_for_timeout(800)
        if net.key(evil, stranger) in net.conn:
            await net.auth(evil, stranger, {'op': 'key', 'k': 'evilkey', 'm': 'nothing'})
            await stranger.pg.fill('.pair .pair-input', '1234'); await stranger.pg.wait_for_timeout(300)
            await net.auth(evil, stranger, {'op': 'key', 'k': 'evilkey', 'm': 'still nothing'})
        ok(evil.id not in stranger.linked and net.key(evil, stranger) not in net.conn, 'a key handed over without knowing the code is refused')
        await stranger.pg.evaluate("() => document.querySelector('.pair .btn')?.click()")
        net.devs.remove(evil); evil.on = False
        # Forget on the iPad
        await ipad.pg.evaluate("() => document.querySelector('[data-panel=app]').click()"); await ipad.pg.wait_for_timeout(600)
        await ipad.pg.evaluate("() => document.querySelector('#pairCard .pair-list button').click()"); await ipad.pg.wait_for_timeout(300)
        await ipad.pg.evaluate("() => document.querySelector('.ask .danger-fill').click()"); await ipad.pg.wait_for_timeout(800)
        lst = await ipad.pg.evaluate("() => document.querySelectorAll('#pairCard .pair-list li').length")
        ok(not ipad.linked and net.key(ipad, phone) not in net.conn and lst == 0 and await peers(phone) == 0, 'Forget: the two no longer connect, the list is empty')
        await restart(phone); await phone.pg.wait_for_timeout(1000)
        ok(net.key(ipad, phone) not in net.conn, 'forgotten: the iPhone started again does not connect')
        # linking again works (the iPhone still remembered the iPad: a new code replaces it)
        await ipad.pg.evaluate("async () => { (await import('/js/pair.js')).openPair(); }")
        await phone.pg.evaluate("async () => { (await import('/js/pair.js')).openPair(); }")
        await phone.pg.wait_for_function("() => { const i = document.querySelector('.pair .pair-input'); return i && !i.hidden; }", timeout=10000)
        await ipad.pg.wait_for_function("() => { const c = document.querySelector('.pair .pair-code'); return c && !c.hidden && c.textContent.trim().length > 0; }", timeout=10000)
        code = await ipad.pg.evaluate("() => document.querySelector('.pair .pair-code').textContent.replace(/\\s/g, '')")
        await phone.pg.fill('.pair .pair-input', code); await phone.pg.wait_for_timeout(800)
        ok(phone.id in ipad.linked and ipad.linked[phone.id]['key'] == phone.linked[ipad.id]['key'] and await peers(phone) == 1, 'linked again with a new code')
        # the plain web version (no app): no linking card, everything as before
        w = await b.new_context(viewport={'width': 1180, 'height': 820}); wp = await w.new_page(); await wp.add_init_script('window.__noTour = true;')
        await wp.goto(f'http://localhost:{PORT}/index.html'); await wp.wait_for_timeout(1500)
        ok(await wp.evaluate("() => document.querySelector('#pairCard').hidden"), 'the web version (no app): no linking card')
        print('log', net.log[-8:])
        print('errors', errs[:4]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'linking once with a code')
        await b.close()
asyncio.run(main())
