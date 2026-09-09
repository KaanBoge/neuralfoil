"""Read-only finite saved binding audit. Never calls prepare or finalizer.run."""
from pathlib import Path
import json, hashlib, types, time
from collections import Counter
from docx import Document

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
EDITION=ROOT/'submission_revision_20260908/renewed_manuscript_v9'
BINDING_SHA='6393f69904cfdedf7c3f3bdde0c0c5b037f3e4611eb37e8a2f33d6bcf7f39432'
PREPARER_SHA='54ec1625c0c2631ee4abb0285627f4d42b57bf5362031b55f2caaadd57e99761'

def audit():
    started=time.monotonic()
    raw=(HERE/'prepare_v9_final_config.py').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PREPARER_SHA
    p=types.ModuleType('authenticated_draft_preparer');p.__file__=str(HERE/'prepare_v9_final_config.py')
    exec(compile(raw,p.__file__,'exec'),p.__dict__)
    h=p.helper();pins=h.Pins(ROOT)
    binding_path=pins.pin(p.spec(EDITION/'work/ROOT_V9_PREPARATION_BINDING_v1.json',BINDING_SHA))
    b=json.loads(binding_path.read_text());p.validate_binding(b)
    for path,sha in b['source_pins'].items():pins.pin(p.spec(path,sha))
    a=json.loads(pins.pin(b['assembly_audit']).read_text())
    assert a['result']=='PASS' and h.pointer(a,b['assembly_binding_pointer'])==p.ASSEMBLY_SHA
    pins.pin(b['assembly_review'])
    pins.pin(p.spec(EDITION/'work/ASSEMBLY.json',p.ASSEMBLY_SHA))
    groups=Counter();pages=[]
    for kind,row in p.SELECTORS.items():
        base=EDITION/'work'/('render_'+kind)/'v2'
        pins.pin(p.spec(EDITION/(kind+'.complete.md'),row['source']))
        pins.pin(p.spec(base/'build_documents.py',p.BUILDER_SHA))
        for field,name in [('build','BUILD.json'),('layout','LAYOUT_AUDIT.json'),('page_map','PAGE_MAP.json'),('docx',row['stem']+'.docx'),('pdf',row['stem']+'.pdf')]:
            pins.pin(p.spec(base/name,row[field]))
        layout=json.loads((base/'LAYOUT_AUDIT.json').read_text())
        assert layout['status']=='PASS_PROGRAMMATIC' and not layout['violations']
        assert layout['pages']==row['pages'] and layout['pdf_sha256']==row['pdf']
        current_hashes={str(x['page']):x['png_sha256'] for x in layout['ledger']}
        assert set(current_hashes)==set(b['visual'][kind])
        for n,entry in b['visual'][kind].items():
            current=pins.pin(p.spec(base/('page-'+n+'.png'),current_hashes[n]))
            result=h.visual_page(pins,current,entry)
            pages.append(dict(document=kind,page=int(n),**result))
            groups[(kind,entry['ledger']['path'],entry['ledger']['sha256'])]+=1
    base=EDITION/'work/render_supplement/v2'
    doc=Document(base/(p.SELECTORS['supplement']['stem']+'.docx'))
    page_map=json.loads((base/'PAGE_MAP.json').read_text())
    source=(EDITION/'supplement.complete.md').read_bytes()
    reading=h.reading_source_bytes('supplement',source,b['toc_labels'],page_map)
    for heading,label in b['toc_labels'].items():
        assert any(par.text==label+'\t'+str(page_map[heading]) for par in doc.paragraphs)
    assert len(b['toc_labels'])==14
    pins.reread()
    return dict(status='PASS_READ_ONLY_BINDING_VALIDATION_NOT_PREPARATION',binding_sha256=BINDING_SHA,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        elapsed_seconds=time.monotonic()-started,visual_pages=len(pages),
        main_pages=33,supplement_pages=101,toc_labels=14,
        reading_bytes_computed_in_memory_only=True,reading_sha256=hashlib.sha256(reading).hexdigest(),
        groups=[dict(document=k[0],ledger=k[1],sha256=k[2],pages=v) for k,v in groups.items()],
        files=pins.files,pages=pages,actual_prepare_called=False,scientific_maps_expanded=False)

if __name__=='__main__':print(json.dumps(audit(),indent=2))
