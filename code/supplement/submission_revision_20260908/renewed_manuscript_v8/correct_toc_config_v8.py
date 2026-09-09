"""Versioned S9 navigation correction; preserve all prior inputs and renders.

This prepares an authorized corrected config but does not execute the finalizer.
Every configured short label is independently compared with actual DOCX text.
"""
import difflib
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from docx import Document

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RESEARCH = HERE.parent/'work/renewed_research'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def checked(path,h):
    path=Path(path).absolute()
    assert path.is_relative_to(PROJECT) and not any(p.is_symlink() for p in (path,*path.parents))
    raw=path.read_bytes();assert digest(raw)==h,str(path)
    return raw
def pin(path,h=None):
    path=Path(path).absolute();raw=path.read_bytes()
    h=h or digest(raw);checked(path,h)
    return {'path':str(path.relative_to(PROJECT)),'sha256':h}
def save(path,raw):
    with path.open('xb') as f:f.write(raw)
def encoded(value):return (json.dumps(value,indent=2)+'\n').encode()

def main():
    prior=HERE/'work/ROOT_FINAL_QA_CONFIG_FINAL_v1.json'
    old=json.loads(checked(prior,'023acefc4cc2d956be7fe1cba4563c78200054a73bec57f06538474173d41d19'))
    cfg=json.loads(json.dumps(old));supp=cfg['documents']['supplement']
    diag=RESEARCH/'model_proposal/editorial/v8_config_review/TOC_FAILURE_DIAGNOSIS.md'
    checked(diag,'85d6a6bc4ae0c1b5febb54175b6104761aa2bec0ba4581ccd967d481c6fabe3c')
    key='S9 Incremental harm calibration and complete results'
    assert supp['toc_labels'][key]=='S9 Incremental harm calibration'
    supp['toc_labels'][key]='S9 Harm calibration and confidence comparisons'
    paths={k:PROJECT/supp[k]['path'] for k in ('source','docx','pdf','builder','page_map','reading_source')}
    for k,p in paths.items():checked(p,supp[k]['sha256'])
    page_map=json.loads(paths['page_map'].read_text())
    document=Document(paths['docx'])
    paragraphs=[p.text for p in document.paragraphs]
    for heading,label in supp['toc_labels'].items():
        assert paragraphs.count(label+'\t'+str(page_map[heading]))==1,(heading,label)
    helper=RESEARCH/'independent_environment/final_qa_tools/finalize_v8.py'
    checked(helper,'013bf9d87a7a16d72c75b3e68f6d089997c95cf5abe715541fe23af361ed7570')
    spec=importlib.util.spec_from_file_location('readingsource_helper',helper)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=paths['source'].read_bytes();oldreading=paths['reading_source'].read_bytes()
    newreading=module.reading_source_bytes('supplement',source,supp['toc_labels'],page_map)
    oldline=b'| S9 Incremental harm calibration | 63 |'
    newline=b'| S9 Harm calibration and confidence comparisons | 63 |'
    assert oldreading.count(oldline)==1
    assert newreading==oldreading.replace(oldline,newline)
    changed=''.join(difflib.unified_diff(oldreading.decode().splitlines(True),newreading.decode().splitlines(True),fromfile='supplement.reading.md',tofile='supplement.reading.v2.md'))
    outreading=HERE/'supplement.reading.v2.md'
    save(outreading,newreading)
    supp['reading_source']=pin(outreading,digest(newreading))
    receipt={'status':'GENERATED_EXACT_READING_COPY_WITH_ACTUAL_DOCX_TOC_CHECK',
        'source_sha256':digest(source),'sha256':digest(newreading),'bytes':len(newreading),
        'builder_sha256':digest(Path(__file__).read_bytes()),'prior_reading_sha256':digest(oldreading),
        'all_12_labels_exactly_match_docx':True,'only_S9_reading_line_changed':True,
        'rendered_artifacts_unchanged':True,'source_science_unchanged':True,'diff':changed,
        'toc':{h:{'label':label,'page':page_map[h]} for h,label in supp['toc_labels'].items()}}
    receiptpath=HERE/'work/READING_COPY_v2.json';save(receiptpath,encoded(receipt))
    cfg['root_authorization'].update(at_utc=datetime.now(timezone.utc).isoformat(),
        scope='One corrected V8 technical-finalization attempt and absent-or-identical PDF copy only. No rendered/scientific changes, author approval, public release, rights clearance or submission.',
        correction='First actual finalizer rejected stale S9 short label. Root read full independent diagnosis and now verifies every actual DOCX contents paragraph. Only S9 map and deterministic reading artifact change; preserve first failure/config/reading and all prior reviews.',
        prior_authorized_config_sha256='023acefc4cc2d956be7fe1cba4563c78200054a73bec57f06538474173d41d19')
    for p in (prior,diag,HERE/'work/FINALIZATION_ATTEMPT_1.md',receiptpath,Path(__file__)):
        cfg['evidence'].append({'role':'ancillary',**pin(p),'assertions':[]})
    # Prove that every scientific, render and visual field is unchanged.
    for kind in ('main','supplement'):
        left=json.loads(json.dumps(old['documents'][kind]));right=json.loads(json.dumps(cfg['documents'][kind]))
        if kind=='supplement':
            for field in ('reading_source','toc_labels'):left.pop(field);right.pop(field)
        assert left==right
    assert cfg['evidence'][:len(old['evidence'])]==old['evidence']
    target=HERE/'work/ROOT_FINAL_QA_CONFIG_FINAL_v2.json';raw=encoded(cfg);save(target,raw)
    print(json.dumps({'status':'CORRECTED_CONFIG_PREPARED_NOT_FINALIZED','config_sha256':digest(raw),
        'reading_sha256':digest(newreading),'receipt_sha256':digest(receiptpath.read_bytes()),'diff':changed,
        'all_12_actual_DOCX_TOC_labels_match':True,'pages_source_science_unchanged':True}))

if __name__=='__main__':main()
