import asyncio, json, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = await (await b.new_context()).new_page()
        logs = []; pg.on('console', lambda m: logs.append(m.text[:200])); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async (src) => {
          const mp = await import('/vendor/mediapipe/vision_bundle.mjs'); const G = await import('/js/gaze.js');
          const fileset = { wasmLoaderPath: '/vendor/mediapipe/wasm/vision_wasm_internal.js', wasmBinaryPath: '/vendor/mediapipe/wasm/vision_wasm_internal.wasm' };
          const t0 = performance.now();
          const lm = await mp.FaceLandmarker.createFromOptions(fileset, { baseOptions: { modelAssetPath: '/vendor/mediapipe/face_landmarker.task', delegate: 'CPU' }, runningMode: 'IMAGE', numFaces: 1, outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true });
          const t1 = performance.now();
          const img = new Image(); img.src = src; await img.decode();
          const out = [];
          for (const [flip, k] of [[false, 1], [true, 1]]) {
            const c = document.createElement('canvas'); c.width = img.width * k; c.height = img.height * k; const g = c.getContext('2d'); if (flip) { g.translate(c.width, 0); g.scale(-1, 1); } g.drawImage(img, 0, 0, c.width, c.height);
            const t2 = performance.now(); const res = lm.detect(c); const t3 = performance.now();
            const s = G.measure(res, 0); out.push({ flip, ms: Math.round(t3 - t2), ...Object.fromEntries(Object.entries(s).map(([a, v]) => [a, typeof v === 'number' ? +v.toFixed(3) : v])) });
          }
          return { load: Math.round(t1 - t0), simd: await mp.FilesetResolver.isSimdSupported(), out };
        }""", sys.argv[1])
        print(json.dumps(r, indent=1)); print(errs, [l for l in logs if 'rror' in l][:5]); await b.close()
asyncio.run(main())
