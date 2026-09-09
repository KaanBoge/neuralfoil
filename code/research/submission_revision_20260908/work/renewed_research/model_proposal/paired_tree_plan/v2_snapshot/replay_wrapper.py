"""Source-only reviewed wrapper for later explicitly approved independent replay."""
import argparse, contextlib, io, json, os, time, types, zipfile
from pathlib import Path
import support as s
import runner

CHECKER='uncertainty_review/range_bound_feasibility/paired_checker.py'
CHECKER_SHA='33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b'
ORACLE='tree_range_refinement/feature_relation_oracle_review/oracle.py'
LIMIT=128*2**20

class MemoryBudgetError(MemoryError):
    def __init__(self,record):
        self.record=record;super().__init__('conservative owned-memory gate: '+str(record))

def memory_plan(raw,model_expanded):
    """Estimate simultaneous owned storage by phase, not RSS/allocator theorem.

    Producer canonical JSON has unescaped keys; malformed/noncanonical inputs
    are still rejected by parse/checker. Counts here only anticipate allocation.
    """
    n={'paths':raw.count(b'"empty":'),'edges':raw.count(b'"threshold":'),
       'pairs':raw.count(b'"leaves":')}
    if not 1<=n['paths']<=6000 or n['edges']>84000 or not 1<=n['pairs']<=90000:raise ValueError('preparse cardinality cap')
    # JSON parse owns independent edge dictionaries and witness strings; unlike
    # producer traversal there is no shared prefix-object optimization assumed.
    parsed=1024*n['paths']+512*n['edges']+1024*n['pairs']+2**20
    raw_copies=2*len(raw)  # retained authenticated bytes plus transient text decode
    parse_peak=16*2**20+raw_copies+parsed+model_expanded
    independent_paths=1024*n['paths']+512*n['edges']
    path_boxes=n['paths']*(1024+62*80)
    inventory_json_transients=2*(160*n['edges']+200*n['paths'])
    check_peak=16*2**20+len(raw)+parsed+independent_paths+path_boxes+inventory_json_transients+6*model_expanded+4*2**20
    return dict(n,certificate_bytes=len(raw),model_expanded_bytes=model_expanded,
                parsed_estimate_bytes=parsed,inventory_json_transient_bytes=inventory_json_transients,parse_peak_bytes=parse_peak,
                check_peak_bytes=check_peak,estimated_owned_peak_bytes=max(parse_peak,check_peak),
                limit_bytes=LIMIT,measure='conservative algorithm-owned estimate, NOT RSS')

def enforce_memory(record):
    if record['estimated_owned_peak_bytes']>LIMIT:raise MemoryBudgetError(record)

def parse_json(raw,ledger,identity):
    obj=json.loads(raw)
    ledger.append({'kind':'json_parse','identity':identity,'sha256':s.digest(raw),'bytes':len(raw)})
    return obj

@contextlib.contextmanager
def oracle_reader(expected_raw,expected_pin,ledger):
    """Bind the independent checker's own source read without numeric edits."""
    old=Path.read_bytes;target=s.safe_path(s.ROOT/ORACLE)
    if s.digest(expected_raw)!=expected_pin:raise ValueError('oracle buffer pin')
    def read(path):
        if s.safe_path(path)!=target:raise ValueError('unexpected checker file read')
        ledger.append({'kind':'source_execute_read','path':str(target),'sha256':expected_pin,'bytes':len(expected_raw)})
        return expected_raw
    Path.read_bytes=read
    try:yield
    finally:Path.read_bytes=old

def approval_scope(a,registry_sha):
    expected={'phase':'paired_tree_replay','registry_sha256':registry_sha,'model_sha256':s.MODEL_SHA,
              'domains':['D','R'],'seconds':900,'workers':1,'real_execution_authorized':True}
    for key,value in expected.items():
        if key not in a or type(a[key]) is not type(value) or a[key]!=value:raise ValueError('replay approval scope')
    for key in ('certificate_sha256','producer_complete_sha256','producer_registry_sha256'):
        if type(a.get(key)) is not str or len(a[key])!=64 or any(c not in '0123456789abcdef' for c in a[key]):raise ValueError('predecessor approval identity')
    if a['producer_registry_sha256']!=registry_sha:raise ValueError('producer/replay fixed source registry equality')

def predecessor(c,approval):
    if c.get('status')!='COMPLETE' or c.get('phase')!='paired_tree_producer' or c.get('registry_sha256')!=approval['producer_registry_sha256'] or c.get('model_sha256')!=s.MODEL_SHA:raise ValueError('producer completion chain')
    if c['outputs'].get('certificate.json')!=approval['certificate_sha256']:raise ValueError('producer certificate pin')

def model_expanded(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=7 or set(z.namelist())!={k+'.npy' for k in s.MEMBERS}:raise ValueError('model member inventory')
        total=sum(i.file_size for i in z.infolist())
        if total>8*2**20:raise ValueError('expanded model cap')
    return total

def replay_buffers(raw,model_raw,checker_raw,oracle_raw,oracle_pin,ledger,outputs,out,expected_model_sha,deadline):
    # Bound before certificate JSON allocation or model materialization.
    plan=memory_plan(raw,model_expanded(model_raw))
    outputs['MEMORY_PLAN.json']=s.exclusive(out/'MEMORY_PLAN.json',plan)
    enforce_memory(plan)
    certificate=parse_json(raw,ledger,'certificate')
    arrays=runner.load_arrays(model_raw,ledger)
    checker=types.ModuleType('independent_paired_checker');checker.__file__=str(s.ROOT/CHECKER)
    ledger.append({'kind':'source_execute','path':checker.__file__,'sha256':s.digest(checker_raw)})
    exec(compile(checker_raw,checker.__file__,'exec'),checker.__dict__)
    with oracle_reader(oracle_raw,oracle_pin,ledger):
        result=checker.check(certificate,arrays,deadline,expected_model_sha=expected_model_sha)
    return certificate,result,plan

def execute(args):
    regpath=s.HERE/'REGISTRY_v2.json';apath=s.safe_path(args.approval)
    certpath=s.safe_path(args.certificate);completepath=s.safe_path(args.producer_complete)
    metadata={'phase':'paired_tree_replay','registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'model_sha256':s.MODEL_SHA}
    def work(out,ledger,outputs):
        reg=parse_json(s.read_pinned(regpath,args.registry_sha256,ledger),ledger,'registry')
        ap=parse_json(s.read_pinned(apath,args.approval_sha256,ledger),ledger,'approval');approval_scope(ap,args.registry_sha256)
        runner.authenticate(reg,ledger)
        if os.environ.get('OMP_NUM_THREADS')!='1' or os.environ.get('OPENBLAS_NUM_THREADS')!='1':raise ValueError('one-thread environment')
        completed=parse_json(s.read_pinned(completepath,ap['producer_complete_sha256'],ledger),ledger,'producer_complete');predecessor(completed,ap)
        manifest=parse_json(s.read_pinned(s.ROOT/s.MANIFEST,s.MANIFEST_SHA,ledger),ledger,'original_manifest');runner.named_manifest(manifest)
        old=parse_json(s.read_pinned(s.ROOT/s.STAGE0,s.STAGE0_SHA,ledger),ledger,'original_Stage0')
        raw=s.read_pinned(certpath,ap['certificate_sha256'],ledger)
        model_raw=s.read_pinned(s.ROOT/s.MODEL,s.MODEL_SHA,ledger)
        cp=reg['dependencies'][CHECKER];op=reg['dependencies'][ORACLE]
        cr=s.read_pinned(s.ROOT/CHECKER,cp,ledger);orr=s.read_pinned(s.ROOT/ORACLE,op,ledger)
        cert,result,plan=replay_buffers(raw,model_raw,cr,orr,op,ledger,outputs,out,s.MODEL_SHA,time.monotonic()+900)
        runner.same_stage0(cert,old)
        outputs['REPLAY.json']=s.exclusive(out/'REPLAY.json',result)
        runner.authenticate(reg,ledger)
        for path,pin in ((regpath,args.registry_sha256),(apath,args.approval_sha256),(certpath,ap['certificate_sha256']),(completepath,ap['producer_complete_sha256']),(s.ROOT/s.MODEL,s.MODEL_SHA)):
            s.read_pinned(path,pin,ledger,'end_reauthentication')
        return {'status':'PASS_AUTHENTICATED_INDEPENDENT_REPLAY','counts':result['counts'],'memory':plan,'model_materializations':1,'fits':0,'features_targets_loaded':0}
    return runner.protected_attempt(args.output,metadata,work)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for x in ('registry-sha256','approval','approval-sha256','certificate','producer-complete','output'):p.add_argument('--'+x,required=True)
    print(json.dumps(execute(p.parse_args()),sort_keys=True))
