// Reading a .zip made by another app (a forScore archive, a folder zipped in Files, a library
// exported by another score app): its list of files, then each file on its own, so an archive of
// several gigabytes is never read into memory at once. Stored and deflated entries (the two kinds
// every zip uses); deflated ones are opened by the browser itself (DecompressionStream).

const u16 = (v, o) => v.getUint16(o, true), u32 = (v, o) => v.getUint32(o, true);
async function view(blob, at, len) { return new DataView(await blob.slice(at, at + len).arrayBuffer()); }

export async function isZip(blob) {
  if (!blob || blob.size < 22) return false;
  const v = await view(blob, 0, 4);
  return u32(v, 0) === 0x04034b50;
}

// [{ name, size, packed, method, at }] — folders left out
export async function zipEntries(blob) {
  // the end record is in the last 64 KB (after an optional comment)
  const tail = Math.min(blob.size, 65557), base = blob.size - tail;
  const t = await view(blob, base, tail);
  let end = -1;
  for (let i = tail - 22; i >= 0; i--) if (u32(t, i) === 0x06054b50) { end = i; break; }
  if (end < 0) throw new Error('not a zip');
  let count = u16(t, end + 10), cdSize = u32(t, end + 12), cdAt = u32(t, end + 16);
  // (a very large archive keeps its numbers in the zip64 records)
  if (cdAt === 0xffffffff || count === 0xffff) {
    const loc = end - 20;
    if (loc >= 0 && u32(t, loc) === 0x07064b50) {
      const z64at = Number(t.getBigUint64(loc + 8, true));
      const z = await view(blob, z64at, 56);
      count = Number(z.getBigUint64(32, true)); cdSize = Number(z.getBigUint64(40, true)); cdAt = Number(z.getBigUint64(48, true));
    }
  }
  const cd = await view(blob, cdAt, cdSize);
  const out = [], dec = new TextDecoder();
  let p = 0;
  for (let k = 0; k < count && p + 46 <= cd.byteLength; k++) {
    if (u32(cd, p) !== 0x02014b50) break;
    const flags = u16(cd, p + 8), method = u16(cd, p + 10);
    let packed = u32(cd, p + 20), size = u32(cd, p + 24);
    const nl = u16(cd, p + 28), xl = u16(cd, p + 30), cl = u16(cd, p + 32);
    let at = u32(cd, p + 42);
    const raw = new Uint8Array(cd.buffer, cd.byteOffset + p + 46, nl);
    const name = (flags & 0x800) ? dec.decode(raw) : dec.decode(raw);   // (UTF-8 either way: names in other code pages are rare)
    // zip64 extra field: the real sizes and place
    let x = p + 46 + nl; const xEnd = x + xl;
    while (x + 4 <= xEnd) {
      const id = u16(cd, x), len = u16(cd, x + 2);
      if (id === 0x0001) {
        let q = x + 4;
        if (size === 0xffffffff) { size = Number(cd.getBigUint64(q, true)); q += 8; }
        if (packed === 0xffffffff) { packed = Number(cd.getBigUint64(q, true)); q += 8; }
        if (at === 0xffffffff) { at = Number(cd.getBigUint64(q, true)); }
      }
      x += 4 + len;
    }
    if (!name.endsWith('/')) out.push({ name, size, packed, method, at });
    p += 46 + nl + xl + cl;
  }
  return out;
}

// One file of the archive, as a Blob.
export async function zipRead(blob, e) {
  const h = await view(blob, e.at, 30);
  if (u32(h, 0) !== 0x04034b50) throw new Error('damaged zip');
  const start = e.at + 30 + u16(h, 26) + u16(h, 28);
  const data = blob.slice(start, start + e.packed);
  if (e.method === 0) return data;
  if (e.method === 8 && typeof DecompressionStream !== 'undefined') {
    const s = data.stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return await new Response(s).blob();
  }
  throw new Error('This archive is packed in a way Stand cannot open.');
}
