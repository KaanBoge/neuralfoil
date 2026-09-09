"""Structural audit only: no assembly, metrics, fits, or rendering."""
from pathlib import Path
import importlib.util,re,json,hashlib,zipfile
from collections import Counter
from lxml import etree
HERE=Path(__file__).resolve().parent;REV=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    spec=importlib.util.spec_from_file_location('assembly_readonly',REV/'assemble_submission.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    examples=['$[2,3]$','$$[2,3]$$',r'\([2,3]\)',r'\[[2,3]\]','`[2,3]`','```python\nx=[2,3]\n```']
    for text in examples:assert a.replace_citations(text+' prose [2,3]',lambda m:'CITE')==text+' prose CITE'
    manifest=json.loads((REV/'work/ASSEMBLY.json').read_text())
    mapping={int(k):v for k,v in manifest['reference_mapping_old_to_current'].items()}
    mainraw=(REV/'manuscript.md').read_text();main=(REV/'main.complete.md').read_text();supp=(REV/'supplement.complete.md').read_text()
    def protected(t):return [s for yes,s in a.citation_segments(t) if yes]
    def citations(t):return [n for yes,s in a.citation_segments(t) if not yes for m in a.PAT.finditer(s) for n in a.nums(m[1])]
    order=list(dict.fromkeys(citations(mainraw)))
    assert mapping=={n:i+1 for i,n in enumerate(order)}
    completeorder=list(dict.fromkeys(citations(main.split('# References',1)[0])))
    assert completeorder==list(range(1,18)),completeorder
    assert main.split('# References',1)[1]==supp.split('# References',1)[1]
    checks={}
    for name,source,dest in [('main',mainraw,main),('supplement_raw',(REV/'supplement.md').read_text(),supp),('theory',(HERE/'SUPPLEMENT_SECTIONS.md').read_text(),supp)]:
        spans=Counter(protected(source));available=Counter(protected(dest))
        assert not spans-available,(name,spans-available)
        checks[name]=sum(spans.values())
    assert 'Section S2.1' not in supp
    assert 'by the projection result above' in supp
    math={}
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    for kind,text,name in [('main',main,'Manuscript'),('supplement',supp,'Supplement')]:
        spans=[p for p in protected(text) if not p.startswith('`')]
        def xml(p):
            with zipfile.ZipFile(p) as z:return etree.fromstring(z.read('word/document.xml'))
        raw=xml(REV/f'work/render_{kind}/raw.docx');final=xml(REV/f'deliverables/NeuralFoil_Measurement_Correction_{name}.docx')
        r=[''.join(n.itertext()) for n in raw.xpath('//m:oMath',namespaces=ns)]
        f=[''.join(n.itertext()) for n in final.xpath('//m:oMath',namespaces=ns)]
        assert r==f
        assert len(spans)==len(f),(kind,len(spans),len(f))
        assert 'NAVIGATION_PLACEHOLDER' not in ''.join(final.itertext())
        math[kind]=len(f)
    result=dict(status='PASS',protected_syntax_tests=len(examples),preserved_source_spans=checks,first_citation_order=completeorder,native_math_counts=math,main_sha256=sha(REV/'main.complete.md'),supplement_sha256=sha(REV/'supplement.complete.md'),assembly_sha256=sha(REV/'assemble_submission.py'),audit_sha256=sha(Path(__file__)))
    (HERE/'CITATION_V2_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()
