# A scanned-looking 10-page score PDF (images, like IMSLP) and a vector one.
import random, img2pdf, io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.pdfgen import canvas as rc
from reportlab.lib.pagesizes import A4
R = random.Random(4)
def page(n, W=2480, H=3508):
    im = Image.new('L', (W, H), 246); d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', 90); f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', 50)
    except Exception: f = f2 = None
    top = 300
    if n == 0:
        d.text((W//2, 200), 'Sonata in E minor', fill=20, font=f, anchor='mm'); d.text((W-300, 330), 'Johannes Brahms', fill=20, font=f2, anchor='rm'); top = 480
    sp = 28
    y = top
    while y + 4*sp < H - 200:
        for k in range(5): d.line([(180, y + k*sp), (W-180, y + k*sp)], fill=30, width=4)
        for bx in range(180, W-180+1, (W-360)//4): d.line([(bx, y), (bx, y+4*sp)], fill=30, width=5)
        x = 320
        while x < W-240:
            yy = y + R.randint(-4, 12) * sp/2
            d.ellipse([x-20, yy-15, x+20, yy+15], fill=25); d.line([(x+18, yy), (x+18, yy-3.4*sp)], fill=25, width=5)
            x += R.randint(70, 140)
        y += 12*sp
    im = im.filter(ImageFilter.GaussianBlur(0.7)).rotate(R.uniform(-0.6, 0.6), fillcolor=246)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=85); return b.getvalue()
open('/home/claude/fixtures/scan10.pdf', 'wb').write(img2pdf.convert([page(i) for i in range(10)]))
c = rc.Canvas('/home/claude/fixtures/vector8.pdf', pagesize=A4)
W, H = A4
for n in range(8):
    if n == 0: c.setFont('Times-Bold', 22); c.drawCentredString(W/2, H-60, 'Cello Suite No. 1'); c.setFont('Times-Roman', 12); c.drawRightString(W-50, H-85, 'J. S. Bach')
    y = H - 120
    while y > 60:
        for k in range(5): c.line(50, y - k*6, W-50, y - k*6)
        x = 70
        while x < W-60:
            yy = y - R.randint(-2, 10)*3; c.circle(x, yy, 3, fill=1); c.line(x+3, yy, x+3, yy+20); x += R.randint(14, 30)
        y -= 64
    c.showPage()
c.save()
print('ok')
# 600 dpi bilevel CCITT G4 pages, like many IMSLP scans
import tempfile, os
tifs = []
for i in range(12):
    im = Image.open(io.BytesIO(page(i))).convert('L').resize((4960, 7016)).point(lambda v: 0 if v < 140 else 255, '1')
    t = tempfile.mktemp(suffix='.tif'); im.save(t, compression='group4', dpi=(600, 600)); tifs.append(t)
open('/home/claude/fixtures/imslp12.pdf', 'wb').write(img2pdf.convert(tifs))
for t in tifs: os.remove(t)
print('ccitt ok')
