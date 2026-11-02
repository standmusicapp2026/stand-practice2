#!/bin/bash
# A copy of the app for the WebKit test runs. WebKit on Linux (unlike Safari on the iPad) cannot keep
# Blobs in IndexedDB: in this test copy only, db.js turns Blobs into bytes on the way in and back
# into Blobs on the way out. Nothing else changes.
set -e
SRC=${1:-/home/claude/s24/Payload/Stand.app/www}; DST=${2:-/home/claude/wwwsnap}
rm -rf "$DST"; cp -R "$SRC" "$DST"
python3 - "$DST/js/db.js" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
codec = """
const __isBlob = (v) => typeof Blob !== 'undefined' && v instanceof Blob;
async function __enc(v) {
  if (__isBlob(v)) return { __wkblob: await v.arrayBuffer(), type: v.type, name: v.name };
  if (Array.isArray(v)) return Promise.all(v.map(__enc));
  if (v && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) { const o = {}; for (const [k, x] of Object.entries(v)) o[k] = await __enc(x); return o; }
  return v;
}
function __dec(v) {
  if (v && typeof v === 'object' && v.__wkblob instanceof ArrayBuffer) return v.name ? new File([v.__wkblob], v.name, { type: v.type }) : new Blob([v.__wkblob], { type: v.type });
  if (Array.isArray(v)) return v.map(__dec);
  if (v && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) { for (const k of Object.keys(v)) v[k] = __dec(v[k]); return v; }
  return v;
}
"""
s = s.replace("export const db = {", codec + "export const db = {", 1)
s = s.replace("get(store, key) { return withDb((d) => wrap(d.transaction(store).objectStore(store).get(key))); },", "get(store, key) { return withDb((d) => wrap(d.transaction(store).objectStore(store).get(key))).then(__dec); },")
s = s.replace("all(store) { return withDb((d) => wrap(d.transaction(store).objectStore(store).getAll())); },", "all(store) { return withDb((d) => wrap(d.transaction(store).objectStore(store).getAll())).then(__dec); },")
s = s.replace("byIndex(store, index, value) { return withDb((d) => wrap(d.transaction(store).objectStore(store).index(index).getAll(value))); },", "byIndex(store, index, value) { return withDb((d) => wrap(d.transaction(store).objectStore(store).index(index).getAll(value))).then(__dec); },")
s = s.replace("put(store, value) { return withDb((d) => { const tx = d.transaction(store, 'readwrite'); tx.objectStore(store).put(value); return done(tx); }); },", "put(store, value) { return __enc(value).then((ev) => withDb((d) => { const tx = d.transaction(store, 'readwrite'); tx.objectStore(store).put(ev); return done(tx); })); },")
assert s.count('.then(__dec)') == 3 and '__enc(value)' in s, 'db.js changed: update wksnap.sh'
open(p, 'w').write(s)
PY
echo "webkit test copy ready: $DST"
