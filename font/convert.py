"""source/ 의 원본 폰트를 webfont/ 에 .woff2 로 변환한다.
새 폰트를 추가했을 때: python convert.py 만 다시 실행하면 된다."""
import os, glob
from fontTools.ttLib import TTFont

os.makedirs("webfont", exist_ok=True)
total_in = total_out = 0
for src in sorted(glob.glob("source/*/*.ttf") + glob.glob("source/*/*.otf")):
    fam  = os.path.basename(os.path.dirname(src))
    name = os.path.splitext(os.path.basename(src))[0]
    outdir = os.path.join("webfont", fam); os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, name + ".woff2")
    f = TTFont(src)
    f.flavor = "woff2"
    f.save(dst)
    si, so = os.path.getsize(src), os.path.getsize(dst)
    total_in += si; total_out += so
    print(f"{si/1048576:6.2f}MB -> {so/1048576:5.2f}MB  {dst}")
print(f"\n합계 {total_in/1048576:.1f}MB -> {total_out/1048576:.1f}MB ({100-total_out/total_in*100:.0f}% 절감)")
