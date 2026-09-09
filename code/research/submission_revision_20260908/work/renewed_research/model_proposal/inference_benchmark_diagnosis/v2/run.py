"""Explicitly approved single SG diagnostic; source import is data-inert."""
import argparse,datetime,json,os,platform,signal,sys,time
from pathlib import Path
import numpy as np
import diagnostic as d
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[5]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def runtime():return {'python':platform.python_version(),'executable':str(Path(sys.executable).resolve()),'numpy':np.__version__,'numpy_configuration':np.show_config(mode='dicts')}
def authenticate(args,ledger):
    reg=d.parse(d.read(HERE/'REGISTRY.json',args.registry_sha256,ledger),'registry',ledger)
    for name,pin in reg['sources'].items():d.read(HERE/name,pin,ledger)
    ap=d.parse(d.read(args.approval,args.approval_sha256,ledger),'approval',ledger)
    exact={'registry_sha256':args.registry_sha256,'phase':'sg_reference_diagnostic','actual_execution_authorized':True,'seconds':120,'workers':1,'rows':242,'output_cap_bytes':d.CAP,
           'members':reg['members'],'output_path':str(d.safe(HERE/'actual_attempt_1')),'runtime':reg['runtime'],'entrypoint_sha256':reg['sources']['run.py']}
    if set(ap)!=set(exact):raise ValueError('exact approval key set')
    if any(type(ap.get(k)) is not type(v) or ap[k]!=v for k,v in exact.items()):raise ValueError('exact approval contract')
    if ap.get('members')!=reg['members']:raise ValueError('approved member inventory')
    if runtime()!=reg['runtime']:raise ValueError('runtime mismatch')
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']):raise ValueError('one thread')
    return reg
def main(args):
    out=d.safe(HERE/'actual_attempt_1');out.mkdir(exist_ok=False)
    ledger=[];outputs={};start=time.monotonic();meta={'start_utc':now(),'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'pid':os.getpid(),'runtime':runtime()}
    old=signal.getsignal(signal.SIGALRM);term=signal.getsignal(signal.SIGTERM)
    def timeout(*_):raise TimeoutError('120 second total guard')
    signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGTERM,timeout);signal.setitimer(signal.ITIMER_REAL,120)
    try:
        outputs['ATTEMPT.json']=d.save(out,'ATTEMPT.json',meta)
        reg=authenticate(args,ledger)
        authenticated={path:d.read(PROJECT/path,pin,ledger) for path,pin in reg['inputs'].items()}
        raw={name:authenticated[path] for name,path in reg['roles'].items()}
        artifact=d.parse(raw['model'],'model JSON',ledger)
        arrays=d.arrays(raw['references'],ledger)
        buffers={module:(PROJECT/reg['roles'][role],raw[role]) for module,role in [('sg_prepared','prepared'),('sg_portable','portable'),('sg_native','native')]}
        with d.modules(buffers,ledger) as mods:result=d.evaluate(arrays,artifact,mods)
        outputs['DIAGNOSTICS.json']=d.save(out,'DIAGNOSTICS.json',result)
        authenticate(args,ledger)
        for path,pin in reg['inputs'].items():d.read(PROJECT/path,pin,ledger)
        outputs['ACCESS.json']=d.save(out,'ACCESS.json',ledger)
        complete=dict(meta,status='COMPLETE_DIAGNOSTIC_INVENTORY_ONLY',finish_utc=now(),seconds=time.monotonic()-start,outputs=outputs,rows=242,NPZ_materializations=len(d.KEYS),inference_calls=3,benchmark_timings=0,fits=0)
        pin=d.save(out,'COMPLETE.json',complete);print(json.dumps({'complete_sha256':pin,'status':complete['status']}))
    except BaseException as exc:
        d.save(out,'FAILURE.json',dict(meta,status='FAILED_NO_RETRY',finish_utc=now(),seconds=time.monotonic()-start,error=repr(exc),outputs=outputs,access=ledger));raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old);signal.signal(signal.SIGTERM,term)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['registry-sha256','approval','approval-sha256']:p.add_argument('--'+name,required=True)
    main(p.parse_args())
