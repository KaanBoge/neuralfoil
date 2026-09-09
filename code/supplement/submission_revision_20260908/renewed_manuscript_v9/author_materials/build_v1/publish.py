"""Validate exact prose and publish the visually reviewed author-only files exclusively."""
import hashlib, io, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from docx import Document
from pypdf import PdfReader
from PIL import Image
import build

HERE=Path(__file__).resolve().parent
A=HERE.parent
RENDERS={'COVER_LETTER_DRAFT':('render_cover',1), 'HIGHLIGHTS_DRAFT':('render_highlights',1), 'RESEARCH_BRIEF':('render_brief',2)}
OBS={('COVER_LETTER_DRAFT',1):'Title, unsigned status, letter and author approvals fit one page; readable punctuation and no clipping or overlap.',
     ('HIGHLIGHTS_DRAFT',1):'All five bullets and author-review caveat readable; coherent spacing, no clipped glyphs.',
     ('RESEARCH_BRIEF',1):'Questions 1–3 and all section pointers readable; complete question 3 ends before page break.',
     ('RESEARCH_BRIEF',2):'Questions 4–6, numerical percentages, eight-tree exclusion and author limitations readable; no split heading or clipping.'}
def sha(b): return hashlib.sha256(b).hexdigest()
def norm(t): return re.sub(r'\s+','',t.replace('•','').replace('\uf0b7',''))
def main():
    dest=A/'deliverables'
    if dest.exists(): raise FileExistsError(dest)
    result={'status':'PASS_AUTHOR_PREPARATION_ONLY','utc':datetime.now(timezone.utc).isoformat(), 'python':sys.version,
            'sources':{},'tools':{},'documents':{},'visual_ledger':[],
            'text_policy':'Exact literal prose and heading punctuation retained as requested; Markdown syntax removed. No heading wording transformations. Intentional draft/private/unsigned labels retained.',
            'visual_method':'Every page individually inspected at original 1547 by 2002 pixel resolution; not contact-sheet or text-only QA.',
            'scope':'Three author drafts only; no human approval, submission, rights clearance or scientific-package modification.'}
    payloads={}
    for name,(folder,count) in RENDERS.items():
        source=A/(name+'.md');raw=source.read_bytes();assert sha(raw)==build.PINS[name]
        result['sources'][str(source)]=sha(raw)
        docraw=(HERE/'docx'/(name+'.docx')).read_bytes();doc=Document(io.BytesIO(docraw))
        expected=[t.replace('**','') for _,t in build.blocks(raw.decode())]
        assert [p.text for p in doc.paragraphs]==expected
        pdfpath=HERE/folder/(name+'.pdf');pdfraw=pdfpath.read_bytes();pdf=PdfReader(io.BytesIO(pdfraw))
        assert len(pdf.pages)==count
        actual='\n'.join(p.extract_text() for p in pdf.pages)
        assert norm(actual)==norm('\n'.join(expected)), name+' PDF prose mismatch'
        assert not doc.core_properties.author and not doc.core_properties.last_modified_by
        assert not pdf.metadata.get('/Author','')
        result['documents'][name]={'pages':count,'docx_sha256':sha(docraw),'pdf_sha256':sha(pdfraw),'ordered_docx_prose':'EXACT','pdf_prose_ignoring_whitespace_and_generated_bullets':'EXACT','author_metadata':'BLANK'}
        for page in range(1,count+1):
            p=HERE/folder/f'page-{page}.png'
            with Image.open(p) as im: size=list(im.size)
            result['visual_ledger'].append({'path':str(p),'sha256':sha(p.read_bytes()),'page':page,'pixels':size,'status':'PASS','observed':OBS[name,page]})
        payloads[name+'.docx']=docraw;payloads[name+'.pdf']=pdfraw
    paths=[HERE/'build.py',Path(__file__),HERE/'BUILD.json',Path('/PATH_TO_YOUR_HOME/.codex/plugins/cache/openai-primary-runtime/documents/26.905.11957/skills/documents/render_docx.py'),Path('/PATH_TO_YOUR_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/MacOS/soffice')]
    result['tools']={str(p):sha(p.read_bytes()) for p in paths}
    dest.mkdir()
    for name,b in payloads.items():
        with (dest/name).open('xb') as f:f.write(b)
    result['outputs']={str(dest/n):{'sha256':sha(b),'bytes':len(b)} for n,b in payloads.items()}
    with (HERE/'FINAL_QA.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
