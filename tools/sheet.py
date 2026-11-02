import sys
from PIL import Image
ks=sys.argv[2].split(','); out=sys.argv[1]
Wd=Image.new('RGB',(300*len(ks),424))
for i,k in enumerate(ks): Wd.paste(Image.open('/home/claude/covers_out/t/%s.jpg'%k),(i*300,0))
Wd.save(out)
