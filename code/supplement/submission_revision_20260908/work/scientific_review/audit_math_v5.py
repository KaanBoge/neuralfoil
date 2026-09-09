from pathlib import Path
from copy import deepcopy
import hashlib,json,zipfile,xml.etree.ElementTree as E
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
NS={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def tag(s):a,b=s.split(':');return '{'+NS[a]+'}'+b
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with zipfile.ZipFile(p) as z:return E.fromstring(z.read('word/document.xml'))
def stripped(node):
    node=deepcopy(node)
    for p in node.iter():
        for c in list(p):
            if c.tag in {tag('m:nor'),tag('w:i'),tag('w:iCs')}:p.remove(c)
    for p in node.iter():
        for c in list(p):
            if c.tag==tag('w:rPr') and not len(c) and not c.attrib:p.remove(c)
    return E.tostring(node)
def main():
    name='NeuralFoil_Measurement_Correction_Manuscript.docx'
    old=ROOT/'work/render_main/v4'/name
    new=ROOT/'work/render_main/v5'/name
    if not new.exists():new=ROOT/'deliverables'/name
    x,y=load(old),load(new)
    xm=x.findall('.//m:oMath',NS);ym=y.findall('.//m:oMath',NS)
    assert len(xm)==len(ym)
    assert [[n.text for n in o.iter(tag('m:t'))] for o in xm]==[[n.text for n in o.iter(tag('m:t'))] for o in ym]
    assert [stripped(o) for o in xm]==[stripped(o) for o in ym]
    xr=x.findall('.//m:r',NS);yr=y.findall('.//m:r',NS);assert len(xr)==len(yr)
    changed=[];untouched=0
    for a,b in zip(xr,yr):
        sty=a.find('m:rPr/m:sty',NS)
        if sty is not None and sty.get(tag('m:val'))=='p':
            assert b.find('m:rPr/m:nor',NS) is not None
            for k in ['w:i','w:iCs']:assert b.find('w:rPr/'+k,NS).get(tag('w:val'))=='0'
            changed.append(''.join(n.text or '' for n in b.iter(tag('m:t'))))
        else:
            assert E.tostring(a)==E.tostring(b);untouched+=1
    pages=list(range(4,17))+[22,23]
    result={'status':'PASS','math_objects':len(xm),'math_text_identical':True,'math_structure_identical_after_only_style_removal':True,
            'plain_style_runs':len(changed),'unchanged_other_math_runs':untouched,'plain_texts':changed,
            'docx_sha256':{'v4':sha(old),'v5':sha(new)},'build_code_sha256':sha(ROOT/'build_documents.py'),
            'visually_inspected_png_sha256':{str(n):sha(ROOT/f'work/render_main/v5/page-{n}.png') for n in pages}}
    (HERE/'MATH_V5_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
