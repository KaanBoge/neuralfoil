"""Independent read-only metadata review; never imports or executes finalizer."""
from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
from datetime import datetime,timezone
ROOT=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
OUT=Path(__file__).parent
CONFIG=ROOT/'submission_revision_20260908/renewed_manuscript_v8/work/ROOT_FINAL_QA_CONFIG_DRAFT_v2.json'
EXPECTED='c7438e8ef28d53c6e324bf632f6a56cc882671a7b2d1a6a58a07a8662944f7cd'
files={}; records=[]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def pin(path,h):
    p=Path(path);p=p if p.is_absolute() else ROOT/p
    assert p.resolve().is_relative_to(ROOT),p
    assert not any(q.is_symlink() for q in [p,*p.parents]),p
    assert digest(p)==h,('hash',str(p),h)
    assert str(p) not in files or files[str(p)]==h
    files[str(p)]=h
    return p
def spec(s):return pin(s['path'],s['sha256'])
def ptr(x,p):
    for k in p.strip('/').split('/') if p else []:
        k=k.replace('~1','/').replace('~0','~');x=x[int(k)] if isinstance(x,list) else x[k]
    return x
def join(base,p):return Path(p) if Path(p).is_absolute() else ROOT/base/p
def main():
    c=json.loads(pin(CONFIG,EXPECTED).read_bytes());assert c['finalization_authorized'] is False
    final=ROOT/'submission_revision_20260908/work/renewed_research/independent_environment/final_qa_tools/finalize_v8.py'
    pin(final,'013bf9d87a7a16d72c75b3e68f6d089997c95cf5abe715541fe23af361ed7570')
    for e in c['evidence']:
        p=spec(e);d=json.loads(p.read_bytes()) if any(e.get(k) for k in ['assertions','maps','record_lists','scalar_pins']) else None
        for a in e.get('assertions',[]):assert ptr(d,a['pointer'])==a['equals'],(e['role'],a)
        for m in e.get('maps',[]):
            v=ptr(d,m['pointer']);assert isinstance(v,dict) and v
            for name,h in v.items():pin(join(m['base'],name),h)
        for m in e.get('record_lists',[]):
            v=ptr(d,m['pointer']);assert isinstance(v,list) and v
            for row in v:pin(join(m['base'],row['path']),row['sha256'])
        for m in e.get('scalar_pins',[]):pin(m['path'],ptr(d,m['pointer']))
        records.append({'role':e['role'],'path':e['path'],'assertions':e.get('assertions',[]),'maps':e.get('maps',[]),'sha256':e['sha256']})
    evidence_unique=len(files)-2
    roles={e['role'] for e in c['evidence']}
    new={'qualified_displays','qualified_display_review','qualified_arithmetic_review','qualified_h_report','qualified_kl_report','qualified_h_portable','qualified_kl_portable','qualified_h_replay','qualified_kl_default_replay','qualified_kl_isolated_replay','paired_sole_model_producer','paired_sole_model_replay','paired_sole_model_review'}
    assert new<=roles
    old=json.loads(spec(c['old_qa']).read_bytes());assert len(old['files'])==754 and old['unique_old_study_files_reauthenticated']==563 and old['status']=='PASS_TECHNICAL_PREPARATION'
    for p,h in old['files'].items():pin(join(c['old_qa']['base'],p),h)
    docs={};visual=[]
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
    for kind,d in c['documents'].items():
        p={k:spec(d[k]) for k in ['source','builder','build','layout','page_map','docx','pdf']}
        assert all(p[k].parent.name==d['version'] for k in ['build','layout','page_map','docx','pdf'])
        b=json.loads(p['build'].read_bytes());l=json.loads(p['layout'].read_bytes());pm=json.loads(p['page_map'].read_bytes())
        assert (b['source_sha256'],b['builder_sha256'],b['docx_sha256'])==tuple(d[k]['sha256'] for k in ['source','builder','docx'])
        assert l['status']=='PASS_PROGRAMMATIC' and l['violations']==[] and l['pdf_sha256']==d['pdf']['sha256'] and l['pages']==d['pages']
        assert {x['page'] for x in l['ledger']}==set(range(1,d['pages']+1)) and set(d['visual'])=={str(i) for i in range(1,d['pages']+1)}
        for row in l['ledger']:
            current=pin(p['pdf'].parent/f"page-{row['page']}.png",row['png_sha256']);v=d['visual'][str(row['page'])]
            lp=spec(v['ledger']);ledger=json.loads(lp.read_bytes());r=ptr(ledger,v['record_pointer'])
            rp=spec(v['report']);vp=spec(v['reviewed_png']);vd=spec(v['reviewed_pdf'])
            assert rp.stat().st_size and r['page']==v['reviewed_page'] and r['result']=='PASS' and r['individually_viewed_original_resolution'] is True
            assert ledger['pdf_sha256']==v['reviewed_pdf']['sha256'] and r['png_sha256']==v['reviewed_png']['sha256']==row['png_sha256']
            visual.append({'document':kind,'page':row['page'],'lineage':'direct_existing_attestation' if current==vp and vd==p['pdf'] else 'inherited_full_png_identity','reviewed_page':r['page'],'reviewed_png':str(vp),'png_sha256':row['png_sha256']})
        text=p['source'].read_text();images=[]
        for rel in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):
            q=(p['source'].parent/rel.strip('<>')).resolve();assert str(q) in files;images.append(str(q))
        if kind=='supplement':
            reading=spec(d['reading_source']);assert text.count('NAVIGATION_PLACEHOLDER')==1
            headings=re.findall(r'^# (S[0-9]+ [^\n]+|References)[ \t]*$',text,re.M)
            assert set(headings)==set(d['toc_labels'])
            toc='\n'.join(['| Section | PDF page |','| --- | ---: |']+['| '+d['toc_labels'][h]+' | '+str(pm[h])+' |' for h in headings])
            assert reading.read_text()==text.replace('NAVIGATION_PLACEHOLDER',toc)
        with zipfile.ZipFile(p['docx']) as z:
            x=ET.fromstring(z.read('word/document.xml'))
            actual=[b['equations'],len(x.findall('.//m:oMath',ns)),len(x.findall('.//w:tbl',ns)),len(x.findall('.//wp:inline',ns))]
            assert actual==c['content_contract'][kind]
            paragraphs=[''.join(t.itertext()) for t in x.findall('./w:body/w:p',ns)]
            refs=[int(m[1]) for t in paragraphs if (m:=re.match(r'^\[(\d+)\]',t))]
            assert refs==list(range(1,22)),refs
        spec({'path':d['deliverable_docx'],'sha256':d['docx']['sha256']})
        target=ROOT/d['deliverable_pdf'];assert not target.exists() or digest(target)==d['pdf']['sha256']
        docs[kind]={'version':d['version'],'pages':d['pages'],'counts':actual,'references':refs,'markdown_images':images,'artifacts':{k:d[k] for k in p},'pdf_alias_currently_exists':target.exists()}
    direct=sum(v['lineage']=='direct_existing_attestation' for v in visual)
    assert (len(visual),direct,len(visual)-direct)==(110,89,21)
    excluded=[p for p in files if '/all_context_plan/' in p or '/inference_benchmark_diagnosis/' in p]
    assert not excluded,excluded
    for p,h in files.items():assert digest(Path(p))==h,('end reauthentication',p)
    result={'status':'PASS_CONFIG_METADATA_AND_BINDING_REVIEW_NOT_FINALIZATION','created_utc':datetime.now(timezone.utc).isoformat(),'config_sha256':EXPECTED,'finalizer_sha256':files[str(final)],'review_source_sha256':digest(Path(__file__)),'finalization_authorized':False,'evidence_records':len(records),'evidence_unique_files_excluding_config_and_finalizer':evidence_unique,'all_unique_files_reauthenticated':len(files),'old_qa_files':754,'old_scientific_inherited_scope':563,'new_roles':sorted(new),'documents':docs,'visual_counts':{'total':110,'direct_existing_attestations':89,'inherited_full_png_identity':21,'fresh_visual_inspections_this_review':0},'visual_bindings':visual,'evidence':records,'files':files,'excluded_later_lane_paths':excluded,'scientific_execution':False,'finalizer_executed':False,'files_copied':False}
    with (OUT/'REVIEW.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','evidence_records','evidence_unique_files_excluding_config_and_finalizer','all_unique_files_reauthenticated','visual_counts']}))
if __name__=='__main__':main()
