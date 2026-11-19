// A picture made into a PNG (and the text iOS takes it as), away from the page's own thread: Studio
// hands several of these the frames of a film at once, so they are made side by side on the
// iPhone's and iPad's other cores instead of one after another.
let cv = null;
self.onmessage = async (e) => {
  const { id, bmp } = e.data;
  try {
    if (!cv || cv.width !== bmp.width || cv.height !== bmp.height) cv = new OffscreenCanvas(bmp.width, bmp.height);
    const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height); g.drawImage(bmp, 0, 0); bmp.close && bmp.close();
    const blob = await cv.convertToBlob({ type: 'image/png' });
    const u8 = new Uint8Array(await blob.arrayBuffer());
    let s = ''; const CH = 0x8000;
    for (let i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
    self.postMessage({ id, data: btoa(s) });
  } catch (err) { self.postMessage({ id, error: String(err && err.message || err) }); }
};
