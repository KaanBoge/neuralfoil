"""Fixed label-free feature guard audit. Actual execution needs root approval."""
from pathlib import Path
import argparse,io,json,hashlib,zipfile,types,datetime,time,signal,os,csv
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=HERE.parent/'range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1'
REL=ROOT/'feature_relation_certification/relations.py'
PLAN=ROOT/'feature_relation_certification/FEATURE_GUARD_AUDIT_PLAN.md'
REL_SHA='1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127'
PLAN_SHA='6011824c12b16ca96661a3a18f89e34469e569156d915eb03199dac244418bf2'
MANIFEST_SHA='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
ZIP_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
PINS={'features/X62.npz':('436d6e3082a76d9e6a91063dad6ac5eb42934cf79f138b9a160d5438df472ca0',1820450),
      'features/maps.json':('8829bebed0b8c9c62a6971edc13ca3db50b609b687fabc0320e4d3cc16c2b9f2',629634)}
CONTEXTS=[f'group_{s}_fold_{i}' for s in [20260906,20260908] for i in range(5)]+['strict_source_stec8','strict_source_vol1','strict_source_vol2','strict_source_vol3','strict_source_all_uiuc_volumes','final']
MAP_KEYS={'calibration/'+x for x in CONTEXTS}|{'native/'+x for x in CONTEXTS+['SG_exposed','W_new_challenge']}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def checked(path,pin):
    path=Path(path)
    if any(x.is_symlink() for x in (path,*path.parents)):raise ValueError('symlink input')
    raw=path.read_bytes()
    if sha(raw)!=pin:raise ValueError('authentication '+str(path))
    return raw
def write_json(path,value):
    raw=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def sources(args):
    record=json.loads(checked(HERE/'IMPLEMENTATION_FREEZE.json',args.implementation_sha256))
    for n,h in record['source_sha256'].items():checked(HERE/n,h)
    checked(PLAN,PLAN_SHA);raw=checked(REL,REL_SHA)
    approval=json.loads(checked(args.approval,args.approval_sha256))
    if approval.get('implementation_sha256')!=args.implementation_sha256 or 'feature_guard_audit' not in approval.get('authorized_phases',[]):raise ValueError('audit approval')
    m=types.ModuleType('pinned_relations');exec(compile(raw,str(REL),'exec'),m.__dict__)
    return m
def input_buffers():
    manifest=json.loads(checked(DATA/'manifest.json',MANIFEST_SHA));result={}
    for n,(h,size) in PINS.items():
        if manifest['files'][n]!={'sha256':h,'bytes':size}:raise ValueError('manifest payload mismatch')
        raw=checked(DATA/n,h)
        if len(raw)!=size:raise ValueError('input size')
        result[n]=raw
    return result
def load_features(raw,ledger,rows=8868):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)!=2 or {x.filename for x in infos}!={'X62.npy','BASE_CD.npy'} or sum(x.file_size for x in infos)>8*1024*1024:raise ValueError('NPZ inventory/expansion')
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:X=z['X62']
    ledger.append({'operation':'NPZ member materialization','input':'features/X62.npz','sha256':sha(raw),'member':'X62','shape':list(X.shape),'dtype':str(X.dtype),'bytes':int(X.nbytes)})
    if X.dtype!=np.dtype('float64') or X.shape!=(rows,62):raise ValueError('float64 X62 schema')
    return X
def mappings(raw,rows=8868,check_lengths=True):
    pairs=json.loads(raw,object_pairs_hook=lambda p:p)
    if not isinstance(pairs,list) or len(pairs)!=34:raise ValueError('map inventory')
    result={}
    for key,indices in pairs:
        if key in result or key not in MAP_KEYS or not isinstance(indices,list):raise ValueError('map keys')
        if any(type(x) is not int or not 0<=x<rows for x in indices):raise ValueError('map indices')
        result[key]=indices
    if set(result)!=MAP_KEYS:raise ValueError('map keys')
    if check_lengths:
        for k,n in [('native/final',8371),('native/SG_exposed',242),('native/W_new_challenge',255)]:
            if len(result[k])!=n:raise ValueError('native map count')
    return result
def evaluate(X,relation_guard):
    records=[]
    for i,row in enumerate(X):
        values=[float(v) for v in row]
        finite=bool(np.isfinite(row).all())
        absolute=values[16]==abs(values[0])
        minimum=values[18]==min(values[12],values[13])
        maximum=values[19]==max(values[12],values[13])
        guard=relation_guard(values)
        if guard!=(finite and absolute and minimum and maximum):raise ValueError('independent guard conjunction')
        records.append({'index':i,'all_finite':finite,'absolute_equal':absolute,'minimum_equal':minimum,'maximum_equal':maximum,'guard':guard})
    return records
def summarize(records,maps):
    result={}
    for name,indices in [('master',list(range(len(records))))]+list(maps.items()):
        failed=[i for i in indices if not records[i]['guard']]
        result[name]={'row_instances':len(indices),'unique_indices':len(set(indices)),'pass_instances':len(indices)-len(failed),'failed_instances':len(failed),'violating_indices_in_original_order':failed,
            'nonfinite_indices_in_original_order':[i for i in indices if not records[i]['all_finite']]}
    return result
def execute(args):
    out=HERE/'results'
    if any(x.is_symlink() for x in (out,*out.parents)):raise ValueError('symlink output')
    # Permission/source validation before output reservation and before feature bytes.
    relation=sources(args);out.mkdir(exist_ok=False)
    start=time.monotonic();ledger=[]
    record={'started_UTC':now(),'implementation_sha256':args.implementation_sha256,'approval_sha256':args.approval_sha256,
        'manifest_sha256':MANIFEST_SHA,'parent_archive_sha256':ZIP_SHA,'new_fits':0}
    write_json(out/'ATTEMPT.json',record)
    def timeout(*unused):raise TimeoutError('900-second audit guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900)
    try:
        raw=input_buffers();X=load_features(raw['features/X62.npz'],ledger)
        maps=mappings(raw['features/maps.json']);ledger.append({'operation':'JSON map parse','input':'features/maps.json','sha256':sha(raw['features/maps.json']),'keys':len(maps)})
        rows=evaluate(X,relation.relation_guard);summary=summarize(rows,maps)
        with (out/'rows.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        write_json(out/'counts.json',summary)
        sources(args);input_buffers()
        record.update(status='FIXED_FEATURE_AUDIT_COMPLETE',finished_UTC=now(),seconds=time.monotonic()-start,actual_materializations=ledger,
            end_authentication=True,outputs={p.name:sha(p.read_bytes()) for p in out.iterdir()},
            scope='Retained-row guard compliance only; no tree bounds, predictions, targets or calibration')
        write_json(out/'COMPLETE.json',record)
    except BaseException as exc:
        import traceback
        record.update(exception=repr(exc),traceback=traceback.format_exc(),finished_UTC=now(),seconds=time.monotonic()-start,actual_materializations=ledger)
        write_json(out/'FAILURE.json',record);raise
    finally:signal.alarm(0)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--implementation-sha256',required=True);p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True);a=p.parse_args()
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one worker/thread')
    execute(a)
