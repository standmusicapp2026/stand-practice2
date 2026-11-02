# Stand test kit

Everything used to test Stand (not part of the app build). Restore it like this in a fresh session:

    git clone -b testkit https://github.com/standmusicapp2026/stand-practice2 /tmp/kit
    cp -R /tmp/kit/tools /home/claude/tools; cp -R /tmp/kit/fixtures /home/claude/fixtures; cp -R /tmp/kit/real /home/claude/real

The app itself: branch `stand-2.12` (its `www` files at the top: index.html, css, js, vendor…).
`tools/ws2.sh` serves the app from `$WWW` (default /home/claude/s24/Payload/Stand.app/www —
point `WWW` at the checkout of stand-2.12 instead) and runs a command with it:

    WWW=/path/to/stand-2.12 PORT=8765 bash tools/ws2.sh python3 rename.py

- Full suite: `tools/runall.sh` (set `SP` to a scratch folder with a `t/` dir; results in `t/_summary.txt`,
  every line should say "0 fails 0 errs"; about 40 minutes).
- Capture benchmarks: `mutobench.sh` (clean LilyPond pages vs MIDI), `photobench.sh WWW PORT OUT`
  (phone-photo versions), `capeval.py PDF MIDS PAGES` with `V=1` for each error.
- Drone ear: `keyreal.py` (Casals recording + practice material), `keyear2.py` (synthetic modulations).
- iPhone Play from the PDF: `playfile.py`.

Baseline on 2 Nov 2026: clean pages 98.3% (9726/9890 notes); main remaining errors: notes with
ledger lines inside dense beamed 32nd runs (Cello Suite 3 p.3), the lower voice of double stops.
