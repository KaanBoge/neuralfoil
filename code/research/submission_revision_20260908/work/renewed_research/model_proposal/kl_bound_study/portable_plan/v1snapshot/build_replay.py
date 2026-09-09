"""Finite approved export only. No target/array materialization on import."""
from pathlib import Path
import argparse,io,json,os,signal
import numpy as np
import integrity,export_support,shared
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent;ROOT=STUDY.parents[1]
def checked(path,pin):
    raw=Path(path).read_bytes()
    if integrity.sha(raw)!=pin:raise ValueError('hash '+str(path))
    return raw
def authorize(args):
    registry=json.loads(checked(HERE/'REGISTRY.json',args.registry_sha256))
    for n,h in registry['sources'].items():checked(HERE/n,h)
    approval=json.loads(checked(args.approval,args.approval_sha256))
    if approval.get('registry_sha256')!=args.registry_sha256 or 'export' not in approval.get('authorized_phases',[]):raise ValueError('export approval')
    return registry
def build(args):
    registry=authorize(args);ledger=[];args.data_reads=ledger;payload={}
    parent,_=integrity.verified_members(args.parent,shared.PARENT_SHA,shared.PARENT_MANIFEST)
    def read(p):return checked(p,registry['inputs'][str(p)])
    def put(n,raw):
        if n in payload:raise ValueError('duplicate member')
        payload[n]=raw
        if sum(map(len,payload.values()))>integrity.MAX_BYTES:raise ValueError('256MiB cap')
    for p,h in registry['inputs'].items():checked(p,h)
    info=json.loads(parent['inventory.json'])
    for ctx in info['contexts']:
        for label in shared.LABELS:put(f'scalars/{label}_{ctx}.json',read(STUDY/'calibrate'/f'calibrator_{label}_{ctx}.json'))
    for ctx in info['native_contexts']:
        z=shared.arrays(read(STUDY/'score'/f'inference_{ctx}.npz'),ledger,'KL native/'+ctx)
        old=shared.arrays(parent[f'native/{ctx}.npz'],ledger,'parent native/'+ctx,['indices','BASE_CD','core','anchor','gate'])
        for key in old:np.testing.assert_array_equal(old[key],z[key])
        keys=['indices']+[k for label in shared.LABELS for k in [label,label+'__strength',label+'__effective_fraction',label+'__intervened']]
        out=io.BytesIO();np.savez_compressed(out,**{k:z[k] for k in keys});put(f'predictions/{ctx}.npz',out.getvalue())
        if ctx!='final':put(f'prediction_csv/{ctx}.csv',read(STUDY/'score'/f'predictions_{ctx}.csv'))
    for name in shared.COUNTS:put('expected/'+name+'.csv',read(STUDY/'assess'/(name+'.csv')))
    root_source=read(ROOT/'kl_confidence_production/confidence.py')
    adapter,aw=shared.extract(root_source,['production_root_adapter','calibrate_kl_groups','fit_kl_scalar'])
    adapter='import ast,hashlib,types\nfrom fractions import Fraction as F\n'+adapter+'\ncertified_upper_root,ROOT_AST=production_root_adapter()\n'
    put('code/adapter.py',adapter.encode());put('code/exact_kl.py',read(ROOT/'kl_confidence_design/exact_kl.py'))
    overlay,ow=shared.extract(read(STUDY/'run_experiment.py'),['overlay'])
    put('code/overlay.py',('import numpy as np\nimport pandas as pd\nNEW_LABELS='+repr(shared.LABELS)+'\nEXTERNAL='+repr(shared.EXT)+'\n'+overlay).encode())
    for n in ['shared.py','integrity.py','replay.py','test_portable.py']:put('code/'+n,checked(HERE/n,registry['sources'][n]))
    put('README.md',checked(HERE/'README.md',registry['sources']['README.md']))
    for member,path in registry['evidence'].items():put('evidence/'+member,read(Path(path)))
    # Parent identity authenticates complete old evidence; it is never rebuilt.
    put('PARENT_REQUIREMENTS.json',json.dumps({'archive_sha256':shared.PARENT_SHA,'manifest_sha256':shared.PARENT_MANIFEST,
        'required_members':{n:integrity.sha(v) for n,v in parent.items()},'contexts':info['contexts'],'native_contexts':info['native_contexts']},indent=2).encode())
    put('SOURCE_WITNESS.json',json.dumps({'inputs':registry['inputs'],'adapter_AST':aw,'overlay_AST':ow,'materializations':ledger,
        'bootstrap_references':7,'harm_references':9,'counts':shared.COUNTS},indent=2).encode())
    authorize(args)
    for p,h in registry['inputs'].items():checked(p,h)
    checked(args.parent,shared.PARENT_SHA)
    result=integrity.build_private_zip(payload,args.output)
    export_support.write_exclusive(str(args.output)+'.receipt.json',result);print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True);p.add_argument('--output',required=True);p.add_argument('--registry-sha256',required=True);p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True);args=p.parse_args()
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one thread')
    def guarded():
        def timeout(*unused):raise TimeoutError('900-second export guard')
        signal.signal(signal.SIGALRM,timeout);signal.alarm(900)
        try:return build(args)
        finally:signal.alarm(0)
    export_support.run_attempt(args,guarded)
