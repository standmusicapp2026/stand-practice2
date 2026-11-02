# With BR=webkit every test that asks for Chromium gets WebKit (the engine of Safari on the iPad).
import os
if os.environ.get('BR') == 'webkit':
    try:
        from playwright.async_api import _generated as G
        class _Wk:
            def __init__(self, wk): self._wk = wk
            def __getattr__(self, k): return getattr(self._wk, k)
            async def launch(self, *a, **kw):
                kw.pop('args', None)   # (Chromium's own switches mean nothing to WebKit)
                return await self._wk.launch(*a, **kw)
        G.Playwright.chromium = property(lambda self: _Wk(self.webkit))
    except Exception as e:
        print('wkshim failed', e)
