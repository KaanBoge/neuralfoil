"""Finite metadata-only draft. Prints JSON; never finalizes or reads data tables."""
from pathlib import Path
import hashlib,json
ROOT=next(p for p in Path(__file__).resolve().parents if p.name=='NeuralFoil_Research_Paper')
REV='submission_revision_20260908/'
R=REV+'work/renewed_research/'
V8=REV+'renewed_manuscript_v8/'
V9=REV+'renewed_manuscript_v9/'
U=R+'uncertainty_review/range_bound_feasibility/'
PAIR=R+'model_proposal/paired_tree_plan/'
FOUR=R+'model_proposal/four_tree_matching_plan/'
BENCH=R+'independent_environment/inference_benchmark_plan/'
CACHE=R+'model_proposal/performance_cache_plan/'
PHASES=['preflight','calibrate','score','assess']
def digest(raw):return hashlib.sha256(raw).hexdigest()
def pointer(k):return k.replace('~','~0').replace('/','~1')
class Draft:
    def __init__(self,root):self.root=root;self.reads={};self.evidence=[]
    def read(self,name,expected=None):
        p=(self.root/name).resolve()
        if not p.is_relative_to(self.root.resolve()) or p.suffix not in {'.json','.md','.py','.diff','.txt'}:raise ValueError('metadata/source only')
        if any(x.is_symlink() for x in [self.root/name,*(self.root/name).parents]):raise ValueError('symlink')
        if p.stat().st_size>8*2**20:raise ValueError('bounded metadata')
        raw=p.read_bytes();h=digest(raw)
        if expected is not None and h!=expected:raise ValueError('expected metadata pin')
        if name in self.reads and self.reads[name]!=h:raise ValueError('metadata mutation')
        self.reads[name]=h
        return raw
    def obj(self,name,expected=None):return json.loads(self.read(name,expected))
    def entry(self,role,name,status=True):
        raw=self.read(name);e={'role':role,'path':name,'sha256':digest(raw)}
        if status:
            d=json.loads(raw)
            if not isinstance(d.get('status'),str):raise ValueError('actual status field absent')
            e['assertions']=[{'pointer':'/status','equals':d['status']}]
        self.evidence.append(e);return e
    def maps(self,e,d,specs):
        for key,base in specs:
            values=d[key]
            if not isinstance(values,dict) or not values or not all(isinstance(v,str) and len(v)==64 for v in values.values()):raise ValueError('actual nonempty hash map required')
            e.setdefault('maps',[]).append({'pointer':'/'+key,'base':base})
    def scalar(self,e,d,key,path):
        h=d[key]
        self.read(path,h)
        e.setdefault('scalar_pins',[]).append({'pointer':'/'+key,'path':path})
    def finish(self):
        for n,h in list(self.reads.items()):self.read(n,h)

def build(root=ROOT):
    a=Draft(root)
    old=V8+'work/ROOT_FINAL_QA_CONFIG_FINAL_v2.json'
    legacy=a.obj(old,'8f5ca571dc86f17091dee5a2d8b05b2ef1f677e186618bef0032a928f82f70f3')
    qa=V8+'work/FINAL_TECHNICAL_QA.json';d=a.obj(qa,'ac58346bdc55f51370197788354319ead001f4ae0cbe90ea810b693f3c6fe2b7')
    e=a.entry('v8_frozen_qa',qa);a.maps(e,d,[('files',V8)]);a.scalar(e,d,'config_sha256',old)
    e['scalar_pins'].append({'pointer':'/helper_sha256','path':R+'independent_environment/final_qa_tools/finalize_v8.py'})
    a.read(e['scalar_pins'][-1]['path'],d['helper_sha256'])
    # Finite named successful all-context runs, not newest-directory discovery.
    for family,base in [('paired',PAIR+'all_context_plan/'),('four_tree',FOUR+'all_context_proposal/implementation/')]:
        registry=base+'REGISTRY_v3.json';rd=a.obj(registry)
        for phase,short in [('certificates_produce','producer'),('certificates_replay','replay')]:
            n=base+phase+'/COMPLETE.json';d=a.obj(n);e=a.entry(family+'_all_context_'+short,n)
            a.maps(e,d,[('outputs',base+phase)])
            a.scalar(e,d,'registry_sha256',registry)
            approval=base+('ROOT_'+short.upper()+'_APPROVAL_V3.json' if family=='paired' else 'ROOT_'+phase.upper()+'_APPROVAL.json')
            a.scalar(e,d,'approval_sha256',approval)
            if short=='replay':
                key='producer_complete_sha256' if family=='four_tree' else None
                if key:a.scalar(e,d,key,base+'certificates_produce/COMPLETE.json')
                else:
                    a.read(base+'certificates_produce/COMPLETE.json',d['summary']['predecessor_sha256'])
                    e.setdefault('scalar_pins',[]).append({'pointer':'/summary/predecessor_sha256','path':base+'certificates_produce/COMPLETE.json'})
            reg_e=a.entry('ancillary',registry,False)
            a.maps(reg_e,rd,[('sources',base)])
            if family=='paired':a.maps(reg_e,rd,[('external_sources',R)])
            else:
                for key,v in rd['metadata'].items():
                    if set(v)!={'path','sha256'}:raise ValueError('actual metadata record map')
                    reg_e.setdefault('scalar_pins',[]).append({'pointer':'/metadata/'+pointer(key)+'/sha256','path':R+v['path']})
                for key,v in rd['external_sources'].items():
                    a.read(R+v['path'],v['sha256']);reg_e.setdefault('scalar_pins',[]).append({'pointer':'/external_sources/'+pointer(key)+'/sha256','path':R+v['path']})
    for family,base in [('paired',PAIR+'all_context_downstream_plan/'),('four_tree',FOUR+'downstream_plan/')]:
        rd=a.obj(base+'REGISTRY.json');reg_e=a.entry('ancillary',base+'REGISTRY.json',False)
        a.maps(reg_e,rd,[('sources',base),('external_sources',R)])
        chain=[]
        for phase in PHASES:
            n=base+phase+'/COMPLETE.json';d=a.obj(n);approval=base+'ROOT_'+phase.upper()+'_APPROVAL.json';ap=a.obj(approval,d['approval_sha256'])
            if d['status']!='COMPLETE' or ap['phase']!=phase or ap['predecessor_sha256']!=d['summary']['predecessor_sha256']:raise ValueError('actual approved chain mismatch')
            a.read(base+'REGISTRY.json',d['registry_sha256'])
            chain.append({'phase':phase,'path':n,'sha256':a.reads[n],'approval':{'path':approval,'sha256':a.reads[approval]},'expected_predecessor':ap['predecessor_sha256'],'output_base':base+phase})
        e=a.entry(family+'_downstream_chain',base+'assess/COMPLETE.json');d=a.obj(e['path']);a.maps(e,d,[('outputs',base+'assess')]);e['phase_chain']=chain
        a.scalar(e,d,'registry_sha256',base+'REGISTRY.json')
    a.entry('paired_downstream_review',U+'DOWNSTREAM_ASSESSMENT_REVIEW.md',False)
    a.entry('four_tree_proof_review',U+'four_tree_matching/PROOF_REVIEW.md',False)
    a.entry('four_tree_downstream_review',U+'four_downstream_audit/assessment_attempt_2/REVIEW.md',False)
    # Review receipts are read as metadata; their scientific output maps are
    # specified for later final QA, not materialized in this drafting task.
    for n in ['DOWNSTREAM_PREFLIGHT_QA.json','DOWNSTREAM_CALIBRATION_QA.json','DOWNSTREAM_SCORE_QA.json','DOWNSTREAM_ASSESSMENT_QA.json','DOWNSTREAM_ASSESSMENT_DECISION_QA.json','ALL_CONTEXT_PRODUCER_QA.json','ALL_CONTEXT_REPLAY_QA.json']:
        path=U+n;d=a.obj(path);e=a.entry('ancillary',path)
        for k in ['all_consumed_end_pins','source_sha256']:
            if isinstance(d.get(k),dict) and d[k]:a.maps(e,d,[(k,U)])
    for phase,attempt in [('preflight',1),('calibration',2),('score',1),('assessment',2)]:
        path=U+f'four_downstream_audit/{phase}_attempt_{attempt}/QA.json';d=a.obj(path);e=a.entry('ancillary',path)
        if 'all_consumed_end_pins' in d:a.maps(e,d,[('all_consumed_end_pins',U+'four_downstream_audit')])
    for lane in ['all_context_producer_audit','all_context_replay_audit']:
        a.entry('ancillary',U+'four_tree_matching/'+lane+'/REVIEW.md',False)
    for role,n in [('paired_displays',U+'paired_v9_displays/attempt_1/MANIFEST.json'),('four_tree_displays',V9+'additions/four_v9_displays/attempt_1/MANIFEST.json')]:
        d=a.obj(n);e=a.entry(role,n);base=str(Path(n).parent)
        a.maps(e,d,[('input_sha256',R if role=='four_tree_displays' else '.'),('output_sha256',base),('source_sha256',str(Path(n).parent.parent))])
    # Literal V6 and separately completed request-local run retain their own
    # COMPLETE_REQUIRES_INDEPENDENT_REVIEW status, accompanied by real audits.
    for role,base,attempt,approval,registry in [('timing_completed_run',BENCH,'actual_v6_attempt_1','ROOT_ACTUAL_APPROVAL_V6.json','REGISTRY_v6.json'),('request_local_cache_completed_run',CACHE+'implementation/execution_plan/','actual_attempt_1','ROOT_ACTUAL_APPROVAL.json','REGISTRY.json')]:
        n=base+attempt+'/COMPLETE.json';d=a.obj(n);e=a.entry(role,n);a.maps(e,d,[('outputs',base+attempt)])
        for key,path in [('approval_sha256',base+approval),('registry_sha256',base+registry),('preflight_sha256',base+attempt+'/preflight_COMPLETE.json')]:a.scalar(e,d,key,path)
        rd=a.obj(base+registry);re=a.entry('ancillary',base+registry,False)
        if role=='timing_completed_run':a.maps(re,rd,[('sources',base)])
        else:
            for key,h in rd['sources'].items():
                path=str((root/base/rd['source_paths'][key]).resolve().relative_to(root.resolve()))
                a.read(path,h);re.setdefault('scalar_pins',[]).append({'pointer':'/sources/'+pointer(key),'path':path})
            a.maps(re,rd,[('v6_receipts','.')])
    for role,n,key in [('timing_saved_record_review',R+'model_proposal/editorial/benchmark_v6_actual_review/AUDIT.json','pins'),('request_local_cache_saved_record_review',CACHE+'actual_review/AUDIT.json','file_sha256')]:
        d=a.obj(n);e=a.entry(role,n);a.maps(e,d,[(key,'.')])
    a.entry('timing_reference_contract',BENCH+'V5_HANDOFF.md',False)
    a.entry('request_local_cache_source_review',CACHE+'INDEPENDENT_INTEGRATION_REVIEW.md',False)
    a.entry('ancillary',CACHE+'INDEPENDENT_SOURCE_REVIEW.md',False)
    n=R+'model_proposal/editorial/v9_timing_draft/displays/manifest.json';d=a.obj(n);e=a.entry('timing_displays',n);a.maps(e,d,[('inputs','.'),('outputs',str(Path(n).parent))])
    n=V9+'additions/presentation_blocks_v1/MANIFEST.json';d=a.obj(n);e=a.entry('presentation_block_transform',n);a.maps(e,d,[('outputs',str(Path(n).parent))]);a.scalar(e,d,'script_sha256',V9+'additions/prepare_presentation_blocks.py')
    for key,v in d['sources'].items():
        a.read(v['path'],v['sha256']);e.setdefault('scalar_pins',[]).append({'pointer':'/sources/'+pointer(key)+'/sha256','path':v['path']})
    history=[]
    for phase in ['calibration','assessment']:
        for name in ['FAILURE.json','REVIEW.md']:
            n=U+f'four_downstream_audit/{phase}_attempt_1/'+name;a.read(n);history.append({'role':'historical_failed_review_not_pass','path':n,'sha256':a.reads[n]})
    a.finish()
    return {'status':'DRAFT_EVIDENCE_ONLY_NOT_AUTHORIZED','legacy_config':{'path':old,'sha256':a.reads[old]},'legacy_evidence_unmodified':legacy['evidence'],'legacy_old_qa_unmodified':legacy['old_qa'],'added_evidence':a.evidence,'history_pins':history,'pending_roles':[{'role':'v9_assembly','reason':'not assembled'},{'role':'v9_assembly_audit','reason':'not assembled/audited'},{'role':'four_display_independent_review','reason':'independent display audit pending root selection'}],'authenticated_metadata_and_source_sha256':a.reads,'scope':'Metadata/source/report bytes only. Referenced CSV/NPZ/certificate/archive map targets not read or reauthenticated by this draft. No finalizer/config authorization.'}
if __name__=='__main__':
    import sys
    obj=build();raw=(json.dumps(obj,indent=2)+'\n').encode()
    if sys.argv[1:] in (['--write-draft'],['--write-draft-v2'],['--write-draft-v3']):
        suffix={'--write-draft':'','--write-draft-v2':'_v2','--write-draft-v3':'_v3'}[sys.argv[1]]
        out=Path(__file__).parent/('V9_EVIDENCE_FRAGMENT_DRAFT'+suffix+'.json')
        with out.open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('short draft write')
        print(json.dumps({'status':obj['status'],'sha256':digest(raw),'bytes':len(raw),'metadata_pins':len(obj['authenticated_metadata_and_source_sha256']),'legacy_entries':len(obj['legacy_evidence_unmodified']),'added_entries':len(obj['added_evidence'])}))
    elif not sys.argv[1:]:print(raw.decode(),end='')
    else:raise ValueError('explicit metadata draft mode only')
