"""Read-only render metadata; writes only this review directory."""
from pathlib import Path
import hashlib, json
from PIL import Image
import pdfplumber

OUT = Path(__file__).resolve().parent
REV = OUT.parents[3]
RENDER = REV / 'renewed_manuscript_v7/work/render_supplement/v1'
PDF = RENDER / 'NeuralFoil_Measurement_Correction_Supplement.pdf'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert all((RENDER / f'page-{i}.png').is_file() for i in range(1,69))
rows = []
with pdfplumber.open(PDF) as doc:
    assert len(doc.pages) == 68
    for i in range(1,35):
        p = RENDER / f'page-{i}.png'
        pg = doc.pages[i-1]
        words = pg.extract_words()
        outside = [w for w in words if w['x0'] < 0 or w['top'] < 0 or w['x1'] > pg.width or w['bottom'] > pg.height]
        footer = [w['text'] for w in words if w['top'] > pg.height * .94]
        text = pg.extract_text() or ''
        rows.append(dict(page=i, png_sha256=sha(p), image_size=list(Image.open(p).size),
                         individually_viewed_original_resolution=True,
                         pdf_page_size=[pg.width,pg.height], footer=footer,
                         out_of_page_words=outside, replacement_char_count=text.count('\ufffd'),
                         text_sha256=hashlib.sha256(text.encode()).hexdigest()))
result = dict(pdf=str(PDF),pdf_sha256=sha(PDF),pdf_pages=68,png_pages_present=68,
              inspected_pages=list(range(1,35)),uninspected_pages=list(range(35,69)),pages=rows)
target=OUT/'PAGE_LEDGER.json'
assert not target.exists()
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(pdf_sha256=result['pdf_sha256'],pages=len(rows),outside=sum(len(x['out_of_page_words']) for x in rows),replacement_chars=sum(x['replacement_char_count'] for x in rows),footers=[x['footer'] for x in rows]),indent=2))
