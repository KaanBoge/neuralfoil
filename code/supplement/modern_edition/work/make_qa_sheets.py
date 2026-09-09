"""Pair already-rendered PDF pages for visual layout inspection only."""
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent
source=root/"render_final"
dest=root/"qa_sheets"
dest.mkdir(exist_ok=True)
pages=sorted(source.glob("page-*.png"),key=lambda p:int(p.stem.split("-")[-1]))
for offset in range(0,len(pages),2):
    ims=[Image.open(p).convert("RGB") for p in pages[offset:offset+2]]
    canvas=Image.new("RGB",(sum(im.width for im in ims)+20,max(im.height for im in ims)),"#D9D9D9")
    x=0
    for im in ims:
        canvas.paste(im,(x,0)); x+=im.width+20
    canvas.save(dest/f"pair-{offset//2+1}.png")
print(f"{len(pages)} pages in {(len(pages)+1)//2} paired inspection images")
