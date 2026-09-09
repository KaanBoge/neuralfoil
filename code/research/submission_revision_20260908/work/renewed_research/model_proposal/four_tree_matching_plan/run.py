"""Future sole approved producer entrypoint; source-only until separate approval.

Scientific module is executed from registry-authenticated source bytes only.
"""
import argparse,hashlib,io,json,os,platform,signal,time,types,zipfile
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MODEL='independent_environment/bounds_extraction/arrays/tree_31_capped.npz'
MODEL_SHA='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
PHASE='four_tree_matching_produce'
def utc():return datetime.now(timezone.utc).isoformat()
def strict_approval(a,regsha):
    expected={'phase':PHASE,'registry_sha256':regsha,'model_sha256':MODEL_SHA,'domain':'FINITE_X62_V1','seconds':900,'workers':1,'owned_cap':128*2**20,'output_cap':64*2**20,'real_execution_authorized':True,'output':'attempt_1'}
    pins={'source_review_sha256','synthetic_gate_sha256','checker_registry_sha256'}
    if type(a)!=dict or set(a)!=set(expected)|pins:raise ValueError('exact approval schema')
    if any(type(a[k]) is not type(v) or a[k]!=v for k,v in expected.items()):raise ValueError('approval scope')
    for k in pins:
        if type(a[k])!=str or len(a[k])!=64 or any(c not in '0123456789abcdef' for c in a[k]):raise ValueError('gate/review pin')
def gate_scope(review,gate,regsha):
    cp=review.get('checker_registry_sha256')
    if type(cp)!=str or len(cp)!=64 or any(c not in '0123456789abcdef' for c in cp) or gate.get('checker_registry_sha256')!=cp:raise ValueError('common checker registry gate')
    if review.get('status')!='PASS_SOURCE_REVIEW' or review.get('registry_sha256')!=regsha:raise ValueError('independent source review gate')
    if gate.get('status')!='PASS_FIXED_135000_GATE' or gate.get('registry_sha256')!=regsha or gate.get('pair_classifications')!=135000:raise ValueError('fixed cold synthetic gate')
    for phase,cap in [('producer',128*2**20),('checker',256*2**20)]:
        v=gate[phase]
        if type(v['seconds']) not in (int,float) or not 0<=v['seconds']<=120 or type(v['owned_estimate'])!=int or not 0<=v['owned_estimate']<=cap:raise ValueError('synthetic resource gate')
        if type(v['logical_output_bytes'])!=int or not 0<=v['logical_output_bytes']<=64*2**20:raise ValueError('synthetic output gate')
def module(raw,name,path):
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m
def load_arrays(raw,p,ledger):
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=7 or set(z.namelist())!={k+'.npy' for k in p.MEMBERS}:raise ValueError('exact seven archive members')
        expanded=sum(x.file_size for x in z.infolist())
        if expanded>4*2**20:raise MemoryError('model expanded cap')
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        arrays={}
        for key in p.MEMBERS:
            a=z[key]
            if a.dtype.hasobject:raise ValueError('no object member')
            arrays[key]=a;ledger.append({'operation':'NPZ materialization','member':key,'shape':list(a.shape),'dtype':str(a.dtype),'model_sha256':hashlib.sha256(raw).hexdigest()})
    return arrays
def bind_reference(cert,stage0,replay,manifest,p):
    from fractions import Fraction as F
    def dec(v):return F(int(v['numerator'],16),int(v['denominator'],16))
    if manifest['files'].get('arrays/tree_31_capped.npz')!=MODEL_SHA:raise ValueError('manifest exact model')
    found=[x for x in manifest['trees'] if x.get('context')=='final' and x.get('branch')=='proper']
    if found!=[{'context':'final','branch':'proper','capped':'arrays/tree_31_capped.npz','upper_free':'arrays/tree_31_upper_free.npz'}]:raise ValueError('manifest final/proper identity')
    records=[x for x in stage0['records'] if x['context']=='final']
    if len(records)!=1 or stage0['accessed_tree_sha256']['arrays/tree_31_capped.npz']!=MODEL_SHA:raise ValueError('original Stage0 model')
    old=records[0]
    for k in ('lower','upper'):
        v=old['range'][k]
        if dec(cert['stage0'][k])!=F(int(v['numerator']),int(v['denominator'])):raise ValueError('original Stage0 arithmetic')
    v=old['B_structural']
    if dec(cert['stage0']['B'])!=F(int(v['numerator']),int(v['denominator'])):raise ValueError('original Stage0 B')
    if replay['status']!='PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY' or replay['model_sha256']!=MODEL_SHA:raise ValueError('original replay identity')
    for k in ('lower','upper','B'):
        if dec(cert['original_adjacent'][k])!=dec(replay['summary']['D'][k]):raise ValueError('original D arithmetic')

def execute(args):
    # Bootstrap strictly limited to source/registry/approval bytes. No NPZ here.
    early=[]
    def bootstrap_read(path,pin):
        path=Path(os.path.abspath(path))
        if any(x.is_symlink() for x in (path,*path.parents)) or path.stat().st_size>2**20:raise ValueError('bootstrap path/size')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('bootstrap SHA')
        early.append({'operation':'authenticated_bytes','path':str(path),'sha256':pin,'bytes':len(raw)});return raw
    regraw=bootstrap_read(HERE/'REGISTRY_SOURCE_V1.json',args.registry_sha256)
    reg=json.loads(regraw);early.append({'operation':'JSON parse','identity':'registry','sha256':args.registry_sha256,'bytes':len(regraw)})
    if reg.get('schema')!='FOUR_TREE_SOURCE_REGISTRY_V1' or reg.get('model_sha256')!=MODEL_SHA:raise ValueError('fixed registry')
    if any(Path(n).name!=n for n in reg['sources']):raise ValueError('flat source names')
    sources={n:bootstrap_read(HERE/n,pin) for n,pin in reg['sources'].items()}
    if sources.get('run.py')!=Path(__file__).read_bytes():raise ValueError('executing entry/source identity')
    s=module(sources['io_support.py'],'four_tree_authenticated_io',HERE/'io_support.py')
    approval=s.pinned(HERE/'ROOT_PRODUCER_APPROVAL.json',args.approval_sha256,early)
    ap=s.parse(approval,early,'root approval');strict_approval(ap,args.registry_sha256)
    review=s.parse(s.pinned(HERE/'ROOT_SOURCE_REVIEW.json',ap['source_review_sha256'],early),early,'source review')
    gate=s.parse(s.pinned(HERE/'COLD_GATE_PASS.json',ap['synthetic_gate_sha256'],early),early,'synthetic gate')
    gate_scope(review,gate,args.registry_sha256)
    checkerpath=ROOT/'uncertainty_review/range_bound_feasibility/four_tree_matching/CHECKER_SOURCE_REGISTRY_V1.json'
    cr=s.parse(s.pinned(checkerpath,ap['checker_registry_sha256'],early),early,'checker registry')
    if review['checker_registry_sha256']!=ap['checker_registry_sha256'] or cr.get('producer_registry_sha256')!=args.registry_sha256 or cr.get('sources')!=reg.get('checker_sources'):raise ValueError('checker producer source binding')
    if any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('one worker/thread environment')
    start=time.monotonic();deadline=start+900;store=s.Store(HERE/'attempt_1',deadline);ledger=list(early)
    metadata={'phase':PHASE,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'model_sha256':MODEL_SHA,'domain':'FINITE_X62_V1','start_utc':utc(),'runtime':{'python':platform.python_version(),'platform':platform.platform()},'limits':{k:ap[k] for k in ('seconds','workers','owned_cap','output_cap')}}
    oldhandler=signal.getsignal(signal.SIGALRM)
    def expired(*_):raise TimeoutError('900-second hard producer guard')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:
        store.write_json('ATTEMPT.json',metadata)
        producer=module(sources['producer.py'],'four_tree_authenticated_producer',HERE/'producer.py');ledger.append({'operation':'source execution','identity':'producer.py','sha256':s.digest(sources['producer.py'])})
        producer.runtime();budget=producer.Budget(900);budget.started=start
        refs={}
        for name,entry in reg['predecessors'].items():refs[name]=s.parse(s.pinned(ROOT/entry['path'],entry['sha256'],ledger,2**20),ledger,name)
        if refs['adjacent_complete']['outputs'].get('REPLAY.json')!=reg['predecessors']['adjacent_replay']['sha256']:raise ValueError('replay output pin')
        if refs['adjacent_complete'].get('status')!='COMPLETE':raise ValueError('replay completion')
        pc,rc,pa,ra=(refs[k] for k in ('adjacent_producer_complete','adjacent_complete','adjacent_producer_approval','adjacent_replay_approval'))
        for c,a,phase,name in [(pc,pa,'paired_tree_producer','adjacent_producer_approval'),(rc,ra,'paired_tree_replay','adjacent_replay_approval')]:
            if c.get('phase')!=phase or c.get('model_sha256')!=MODEL_SHA or c.get('registry_sha256')!=reg['predecessors']['adjacent_registry']['sha256'] or c.get('approval_sha256')!=reg['predecessors'][name]['sha256'] or a.get('real_execution_authorized') is not True:raise ValueError('inherited phase approval chain')
        if ra['producer_complete_sha256']!=reg['predecessors']['adjacent_producer_complete']['sha256'] or ra['certificate_sha256']!=pc['outputs']['certificate.json']:raise ValueError('inherited producer/replay ancestry')
        raw=s.pinned(ROOT/MODEL,MODEL_SHA,ledger,8*2**20)
        # Bound all permitted decompression bytes BEFORE np.load materialization.
        budget.check(producer.memory_plan(4*2**20,len(raw),sum(map(len,sources.values())))['estimated_owned_bytes'])
        arrays=load_arrays(raw,producer,ledger)
        cert=producer.construct(arrays,budget,model_sha=MODEL_SHA,source_bytes=sum(map(len,sources.values())),input_bytes=len(raw))
        bind_reference(cert,refs['stage0'],refs['adjacent_replay'],refs['manifest'],producer)
        store.write_json('certificate.json',cert)
        # Reauthenticate all input/source/predecessor buffers and accepted outputs.
        s.pinned(HERE/'REGISTRY_SOURCE_V1.json',args.registry_sha256,ledger)
        s.pinned(HERE/'ROOT_PRODUCER_APPROVAL.json',args.approval_sha256,ledger)
        s.pinned(HERE/'ROOT_SOURCE_REVIEW.json',ap['source_review_sha256'],ledger)
        s.pinned(HERE/'COLD_GATE_PASS.json',ap['synthetic_gate_sha256'],ledger)
        s.pinned(checkerpath,ap['checker_registry_sha256'],ledger)
        for n,pin in reg['sources'].items():s.pinned(HERE/n,pin,ledger)
        for entry in reg['predecessors'].values():s.pinned(ROOT/entry['path'],entry['sha256'],ledger,2**20)
        s.pinned(ROOT/MODEL,MODEL_SHA,ledger,8*2**20);store.verify_outputs(ledger)
        store.write_json('ACCESS.json',ledger)
        receipt=dict(metadata,status='COMPLETE',finish_utc=utc(),elapsed_seconds=time.monotonic()-start,outputs=dict(store.outputs),summary={'counts':cert['counts'],'stage0':cert['stage0'],'original_adjacent':cert['original_adjacent'],'final':cert['final'],'owned_estimate_peak':budget.peak,'measure':'algorithm-owned_not_RSS','model_materializations':1,'features_targets_calibration_loaded':0,'fits':0,'R_used':False})
        store.write_json('COMPLETE.json',receipt);return receipt
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL,0)
        failure=dict(metadata,status='NO_NEW_CERTIFICATE',finish_utc=utc(),elapsed_seconds=time.monotonic()-start,error=repr(exc)[:4096],accepted_outputs=dict(store.outputs),last_access=ledger[-20:])
        store.write_json('FAILURE.json',failure,emergency=True);raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,oldhandler)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--registry-sha256',required=True);a.add_argument('--approval-sha256',required=True)
    print(json.dumps(execute(a.parse_args()),sort_keys=True))
