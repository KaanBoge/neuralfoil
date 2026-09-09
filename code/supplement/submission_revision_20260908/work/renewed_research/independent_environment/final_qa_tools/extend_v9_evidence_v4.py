"""Append two explicitly selected display-review pins; never finalize."""
from pathlib import Path
import copy,json
from draft_v9_evidence import Draft,ROOT,R,V8,V9,U,digest
HERE=Path(__file__).resolve().parent
BASE='2d710279d54ae4db759875b337139bac7132368f9cfcbdcd39f57998d91b212a'
QA='c3915224da748f4755b98de5516e16c76dc24427ef454885bb184cd0ef162ee2'
def extend(base,a):
    result=copy.deepcopy(base)
    n=U+'four_downstream_audit/FOUR_DISPLAY_QA.json';d=a.obj(n,QA)
    if d['status']!='PASS_INDEPENDENT_SAVED_DISPLAY' or d['differences'] or d['fits']!=0 or d['resampling']!=0:raise ValueError('exact completed display audit scope')
    old=next(e for e in result['added_evidence'] if e['role']=='four_tree_displays')
    if d['manifest_sha256']!=old['sha256'] or d['binding_sha256']!='50d47f6464353f485d9e74f28e212f5502ec11608334edcfc1d3dae54941765a':raise ValueError('display predecessor mismatch')
    e=a.entry('four_display_independent_review',n)
    a.maps(e,d,[('input_output_source_pins','.')])
    a.scalar(e,d,'source_sha256',U+'four_downstream_audit/audit_displays.py')
    a.entry('ancillary',U+'four_downstream_audit/FOUR_DISPLAY_REVIEW.md',False)
    result['added_evidence'].extend(a.evidence)
    result['pending_roles']=[e for e in result['pending_roles'] if e['role']!='four_display_independent_review']
    result['authenticated_metadata_and_source_sha256'].update(a.reads)
    result['predecessor_fragment_sha256']=BASE
    return result
def scaffold(fragment,legacy):
    def document(kind):
        fields={k:None for k in ['source','builder','build','layout','page_map','docx','pdf']}
        fields.update(version=None,pages=None,visual=None,deliverable_docx=V9+'deliverables/'+kind+'.docx',deliverable_pdf=V9+'deliverables/'+kind+'.pdf')
        # Delivery aliases are deliberately unset: filenames need explicit root selection.
        fields['deliverable_docx']=fields['deliverable_pdf']=None
        if kind=='supplement':fields.update(reading_source=None,toc_labels=None)
        return fields
    pending=[{'role':e['role'],'path':None,'sha256':None,'pending_reason':e['reason']} for e in fragment['pending_roles']]
    return {'schema':'v9-final-qa-1','finalization_authorized':False,'project_root':str(ROOT),'edition':V9.rstrip('/'),
      'content_contract':{'main':[17,133,4,4],'supplement':[43,343,44,2],'references':23},
      'old_qa':copy.deepcopy(fragment['legacy_old_qa_unmodified']),
      'v8_sources':{k:copy.deepcopy(legacy['documents'][k]['source']) for k in ['main','supplement']},
      'documents':{k:document(k) for k in ['main','supplement']},
      'evidence':copy.deepcopy(fragment['legacy_evidence_unmodified']+fragment['added_evidence'])+pending,
      'history_pins_for_root_ancillary_selection':copy.deepcopy(fragment['history_pins']),
      'scaffold_status':'UNAUTHORIZED_INCOMPLETE_DO_NOT_FINALIZE',
      'unresolved':['Final V9 assembly and independent audit after reader-title/TOC successor','Final document source/builder/build/layout/page-map/DOCX/PDF hashes','Final explicit render versions and page counts','All page-by-page visual witnesses or exact PNG lineage','Final deterministic supplementary reading source and TOC labels','Exact delivery aliases','Root approval of measured native counts after final build'],
      'counts_scope':'Root-supplied current first-render observations only; not final count adoption or authority'}
def write(name,obj):
    raw=(json.dumps(obj,indent=2)+'\n').encode();p=HERE/name
    with p.open('xb') as f:
        if f.write(raw)!=len(raw):raise OSError('short metadata write')
    return {'path':name,'sha256':digest(raw),'bytes':len(raw)}
def main():
    a=Draft(ROOT);base_path=str((HERE/'V9_EVIDENCE_FRAGMENT_DRAFT_v3.json').relative_to(ROOT));base=a.obj(base_path,BASE)
    result=extend(base,a);a.finish()
    legacy=a.obj(base['legacy_config']['path'],base['legacy_config']['sha256'])
    sk=scaffold(result,legacy)
    if result['legacy_evidence_unmodified']!=base['legacy_evidence_unmodified'] or result['added_evidence'][:len(base['added_evidence'])]!=base['added_evidence']:raise ValueError('prior roles changed')
    names=['V9_EVIDENCE_FRAGMENT_DRAFT_v4.json','V9_FINALIZER_SCAFFOLD_UNAUTHORIZED.json']
    if any((HERE/n).exists() for n in names):raise FileExistsError('exclusive metadata outputs')
    a.finish();print(json.dumps([write(names[0],result),write(names[1],sk)]))
if __name__=='__main__':main()
