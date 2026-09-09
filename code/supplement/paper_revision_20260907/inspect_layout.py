"""Read rendered PDFs for navigation and structural diagnostics; visual QA is separate."""
import argparse
import json
import re
from pathlib import Path
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent

def norm(s):
    return re.sub(r'\s+','',s).replace('ﬁ','fi').replace('ﬂ','fl')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('kind');ap.add_argument('render');args=ap.parse_args()
    work=HERE/'work'/args.kind
    pdf=next((HERE/'work'/args.render).glob('*.pdf'))
    pages=PdfReader(pdf).pages
    headings=json.loads((work/'headings.json').read_text())
    texts=[p.extract_text() for p in pages]
    selected=[h for h in headings if h['level']==1 and (h['text'].startswith(('1 ','2 ','3 ','4 ','5 ','6 ','Appendix ')) or h['text']=='References')]
    page_map={}
    for h in selected:
        hits=[i+1 for i,t in enumerate(texts) if norm(h['text']) in norm(t)]
        assert hits,h
        page_map[h['text']]=hits[-1]
    (work/'page_map.json').write_text(json.dumps(page_map,indent=2)+'\n')
    summaries=[]
    for i,t in enumerate(texts,1):
        clean=t.splitlines()
        summaries.append({'page':i,'characters':len(t),'first':' / '.join(clean[:3]),'last':' / '.join(clean[-4:])})
    (work/'page_summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print(json.dumps({'pages':len(pages),'page_map':page_map,'short_pages':[s for s in summaries if s['characters']<650]},indent=2))

if __name__=='__main__': main()
