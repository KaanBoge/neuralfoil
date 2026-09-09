"""Read-only V3 render inventory following individual visual review."""
from pathlib import Path
import hashlib, json
from PIL import Image
import pdfplumber
OUT = Path(__file__).resolve().parent
RENDER = OUT.parents[3] / 'renewed_manuscript_v7/work/render_supplement/v3'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
PDF = RENDER / 'NeuralFoil_Measurement_Correction_Supplement.pdf'
scopes = [
 'S1 source recovery and grouping', 'Identity purging and nominal geometry',
 'S2 Table S1 X24 feature definitions', 'K18 weighting S1 and Table S2 experts 1 to 5',
 'Table S2 repeated header and experts 6 to 27', 'Targets family parameters and gates',
 'Spline simplex kernel and contextual models', 'Global 21 and 27 controls and inference',
 'S3 risk equations S2 to S4', 'Geometry RBF S5 and preserved failure',
 'Neural models and Table S3 ten procedures', 'Oracle equation S6 and scope',
 'S4 roles ranks and counts', 'Scale inference and metric definitions',
 'Bootstrap and tolerances', 'S5 proof scope S7', 'Equations S8 to S12',
 'Equations S13 to S15', 'Equations S16 to S17 and source paths',
 'Certificate reproduction and weighting equation S18', 'Table S4 and sensitivity results',
 'Statistical interpretation boundary', 'S6 connected reproduction',
 'Headline reference reconstruction', 'Explicit and provisioned environments',
 'Matched build and portable certificates', 'Private access boundaries and timings',
 'S7 complete panel results introduction', 'Figure S1 both baseline heatmaps and caption',
 'Table S5 capped full all 31 views', 'Table S6 capped half all 31 views',
 'Table S7 upper free full all 31 views', 'Table S8 upper free half all 31 views']
assert len(scopes) == 33
assert all((RENDER / f'page-{i}.png').is_file() for i in range(1,69))
rows=[]
with pdfplumber.open(PDF) as doc:
    assert len(doc.pages)==68
    for i, scope in zip(range(2,35),scopes):
        pg=doc.pages[i-1]; p=RENDER/f'page-{i}.png'
        words=pg.extract_words(); text=pg.extract_text() or ''
        im=Image.open(p)
        rows.append(dict(page=i,scope=scope,result='PASS',individually_viewed_original_resolution=True,
          png_sha256=sha(p),pixel_sha256=hashlib.sha256(im.tobytes()).hexdigest(),image_size=list(im.size),
          footer=[w['text'] for w in words if w['top']>pg.height*.94],
          out_of_page_words=[w for w in words if w['x0']<0 or w['top']<0 or w['x1']>pg.width or w['bottom']>pg.height],
          replacement_char_count=text.count('\ufffd'),text_sha256=hashlib.sha256(text.encode()).hexdigest()))
pins={p.name:sha(p) for p in RENDER.iterdir() if p.is_file() and not p.name.startswith('page-')}
result=dict(pdf=str(PDF),pdf_sha256=sha(PDF),source_and_build_sha256=pins,pdf_pages=68,png_pages_present=68,
  inspected_pages=list(range(2,35)),uninspected_pages=[1]+list(range(35,69)),pages=rows)
target=OUT/'PAGE_LEDGER.json'; assert not target.exists()
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(pdf_sha256=sha(PDF),ledger_sha256=sha(target),pins=pins,
 outside=sum(len(r['out_of_page_words']) for r in rows),replacement_chars=sum(r['replacement_char_count'] for r in rows),
 footers=[r['footer'] for r in rows]),indent=2))
