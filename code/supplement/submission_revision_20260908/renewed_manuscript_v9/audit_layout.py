"""Check rendered structure against its archived build; visual review is separate."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import pdfplumber
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=['main','supplement'])
    parser.add_argument('version')
    parser.add_argument('--compare')
    args=parser.parse_args()
    if not re.fullmatch(r'v[1-9]\d*',args.version):
        raise ValueError('numbered rendering required')
    folder=HERE/'work'/('render_'+args.kind)/args.version
    pdfs=list(folder.glob('*.pdf'))
    assert len(pdfs)==1,pdfs
    path=pdfs[0]
    build=json.loads((folder/'BUILD.json').read_text())
    assert sha(folder/(args.kind+'.complete.md'))==build['source_sha256']
    assert sha(folder/'build_documents.py')==build['builder_sha256']
    docxs=list(folder.glob('*.docx'))
    assert len(docxs)==1 and sha(docxs[0])==build['docx_sha256']
    reader=PdfReader(path)
    page_map={}
    def walk(items):
        for item in items:
            if isinstance(item,list):walk(item)
            else:page_map[item.title]=reader.get_destination_page_number(item)+1
    walk(reader.outline)
    ledger=[];figures=[];tables=[];violations=[]
    with pdfplumber.open(path) as pdf:
        for number,page in enumerate(pdf.pages,1):
            text=page.extract_text() or ''
            outside=[c['text'] for c in page.chars if c['x0']<-.1 or c['x1']>page.width+.1 or c['top']<-.1 or c['bottom']>page.height+.1]
            page_figures=re.findall(r'^Figure (S?\d+)\.',text,re.M)
            page_tables=re.findall(r'^Table (S?\d+)\.',text,re.M)
            figures+=page_figures;tables+=page_tables
            if outside:violations.append({'page':number,'outside_characters':outside})
            if '\ufffd' in text:violations.append({'page':number,'replacement_character':True})
            if len(page.images)!=len(page_figures):
                violations.append({'page':number,'images':len(page.images),'figure_captions':page_figures})
            if 'NAVIGATION_PLACEHOLDER' in text:
                violations.append({'page':number,'unresolved_navigation':True})
            ledger.append({'page':number,'characters':len(text),'images':len(page.images),
                           'figure_captions':page_figures,'table_captions':page_tables,
                           'outside_characters':len(outside),'png_sha256':sha(folder/f'page-{number}.png')})
    prefix='S' if args.kind=='supplement' else ''
    assert figures==[prefix+str(i) for i in range(1,build['figures']+1)],figures
    assert tables==[prefix+str(i) for i in range(1,build['tables']+1)],tables
    comparison=None
    if args.compare:
        if not re.fullmatch(r'v[1-9]\d*',args.compare):raise ValueError('numbered comparison required')
        prior=folder.parent/args.compare
        comparison={'version':args.compare,'old_pages':len(list(prior.glob('page-*.png'))),
                    'raster_identical_pages':[i for i in range(1,len(ledger)+1) if (prior/f'page-{i}.png').is_file() and sha(prior/f'page-{i}.png')==ledger[i-1]['png_sha256']]}
    result={'status':'PASS_PROGRAMMATIC' if not violations else 'REVISE',
            'visual_review_still_required':True,'kind':args.kind,'version':args.version,
            'pdf_sha256':sha(path),'pages':len(ledger),'page_map':page_map,
            'figure_captions':figures,'table_captions':tables,'violations':violations,
            'ledger':ledger,'comparison':comparison,'code_sha256':sha(Path(__file__))}
    for name,value in [('PAGE_MAP.json',page_map),('LAYOUT_AUDIT.json',result)]:
        dest=folder/name
        payload=json.dumps(value,indent=2)+'\n'
        if dest.exists() and dest.read_text()!=payload:raise FileExistsError(dest)
        if not dest.exists():dest.write_text(payload)
    print(json.dumps({k:result[k] for k in ['status','pages','figure_captions','table_captions','violations','comparison']}))

if __name__=='__main__':main()
