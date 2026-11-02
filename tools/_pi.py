import asyncio, os, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        print(await pg.evaluate("""async (xml) => { const X = await import('/js/compose/musicxml.js'); let sc = X.fromMusicXML(xml); sc = sc.score || sc; return sc.parts.map(p => p.name + ':' + p.inst); }""", open(sys.argv[1]).read()))
        await b.close()
asyncio.run(main())
