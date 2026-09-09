"""Programmatic layout checks complement, never replace, full-page visual review."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import pdfplumber
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['main','supplement']);ap.add_argument('version');ap.add_argument('--compare');a=ap.parse_args()
    folder=HERE/'work'/('render_'+a.kind)/a.version
    files=list(folder.glob('*.pdf'));assert len(files)==1
    path=files[0];reader=PdfReader(path)
    pages={x.title:reader.get_destination_page_number(x)+1 for x in reader.outline if not isinstance(x,list)}
    (folder/'PAGE_MAP.json').write_text(json.dumps(pages,indent=2)+'\n')
    ledger=[];allfigs=[];alltables=[];violations=[]
    with pdfplumber.open(path) as doc:
        for i,page in enumerate(doc.pages,1):
            text=page.extract_text() or ''
            outside=[c['text'] for c in page.chars if c['x0']<-.1 or c['x1']>page.width+.1 or c['top']<-.1 or c['bottom']>page.height+.1]
            figs=re.findall(r'^Figure (S?\d+)\.',text,re.M)
            tables=re.findall(r'^Table (S?\d+)\.',text,re.M)
            allfigs+=figs;alltables+=tables
            if outside:violations.append({'page':i,'outside_characters':outside})
            if '\ufffd' in text:violations.append({'page':i,'replacement_character':True})
            if figs and len(page.images)<len(figs):violations.append({'page':i,'caption_without_image':figs})
            if len(page.images)>len(figs):violations.append({'page':i,'image_without_caption':len(page.images)})
            if 'NAVIGATION_PLACEHOLDER' in text:violations.append({'page':i,'unresolved_navigation':True})
            ledger.append({'page':i,'characters':len(text),'images':len(page.images),'figure_captions':figs,'table_captions':tables,
                           'outside_characters':len(outside),'png_sha256':sha(folder/f'page-{i}.png')})
    if a.kind=='main':
        assert allfigs==['1','2','3'],allfigs
        assert alltables==['1','2','3'],alltables
    else:
        assert allfigs==['S1'],allfigs
        assert alltables==['S'+str(i) for i in range(1,29)],alltables
    comparison=None
    if a.compare:
        old=HERE/'work'/('render_'+a.kind)/a.compare
        comparison={'version':a.compare,'old_pages':len(list(old.glob('page-*.png'))),
                    'raster_identical_pages':[i for i in range(1,len(ledger)+1) if (old/f'page-{i}.png').exists() and sha(old/f'page-{i}.png')==sha(folder/f'page-{i}.png')]}
    result={'status':'PASS_PROGRAMMATIC' if not violations else 'REVISE','visual_review_still_required':True,
            'kind':a.kind,'version':a.version,'pdf_sha256':sha(path),'pages':len(ledger),'page_map':pages,
            'figure_captions':allfigs,'table_captions':alltables,'violations':violations,'ledger':ledger,'comparison':comparison,
            'code_sha256':sha(Path(__file__))}
    (folder/'LAYOUT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','pages','figure_captions','table_captions','violations','comparison']}))

if __name__=='__main__':main()
