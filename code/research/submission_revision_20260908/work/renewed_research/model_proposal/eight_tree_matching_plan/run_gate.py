"""Future one-shot fixed synthetic gate. SOURCE ONLY until explicit approval.

No actual scientific input paths are allowed. Entire entry900s; separately hard
120s preparation/producer/checker phases; all partials and first failure retained.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import time
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=('production_support.py','prototype.py','adapter.py','cold_gate.py','run_gate.py')
HELPERS={
 'old':('model_proposal/four_tree_matching_plan/producer.py','a445462d5faf314ecbd7ea06cb45feb8c26cf99de8d05d246d026b4bbea4b40e'),
 'fixtures':('model_proposal/four_tree_matching_plan/fixtures.py','76d0da75d8f2c4893e9eaa2ee57c50366050d77d33c1eab9bbb20819620d8228'),
 'checker':('uncertainty_review/range_bound_feasibility/eight_tree_matching/checker.py','bf9bf2afae7139eacbb2d0c35e09a3780a567e20cdb11216a525825c511ed792'),
 'old_checker':('uncertainty_review/range_bound_feasibility/four_tree_matching/checker.py','ad4bbdf7b70fd862c959e3d916990890133f5ac4f9af714fb1e5ec6cc7706f1a'),
 'primitive':('uncertainty_review/range_bound_feasibility/paired_checker.py','33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b')}


def stamp():return datetime.now(timezone.utc).isoformat()


def gate_approval(a,regsha,entrysha):
    required=dict(phase='fixed_eight_synthetic_gate',registry_sha256=regsha,
                  entrypoint_sha256=entrysha,output='synthetic_gate_attempt_1',
                  seconds=900,subphase_seconds=120,workers=1,producer_owned_cap=128*2**20,
                  checker_owned_cap=256*2**20,output_cap=64*2**20,
                  python='3.13.9',synthetic_execution_authorized=True)
    if type(a)!=dict or set(a)!=set(required)|{'source_review_sha256'}:
        raise ValueError('exact gate approval fields')
    if any(type(a[k]) is not type(v) or a[k]!=v for k,v in required.items()):
        raise ValueError('gate scope')
    h=a['source_review_sha256']
    if type(h)!=str or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):
        raise ValueError('source review pin')


def execute(args):
    started=time.monotonic();deadline=started+900
    handler=signal.getsignal(signal.SIGALRM)
    def expired(*_):raise TimeoutError('whole-entry900s gate')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    store=None;ledger=[]
    metadata=dict(phase='fixed_eight_synthetic_gate',start_utc=stamp(),
                  registry_sha256=args.registry_sha256,approval_sha256=args.approval_sha256)
    try:
        def boot(path,pin):
            p=Path(os.path.abspath(path))
            if any(x.is_symlink() for x in (p,*p.parents)) or p.stat().st_size>2**20:raise ValueError('source bootstrap path')
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('source bootstrap hash')
            ledger.append(dict(operation='authenticated_source_bytes',path=str(p),sha256=pin,bytes=len(raw)))
            return raw
        regraw=boot(HERE/'GATE_REGISTRY.json',args.registry_sha256)
        if 384*len(regraw)>8*2**20:raise MemoryError('preparse registry8MiB')
        reg=json.loads(regraw)
        if set(reg)!={'schema','sources','helpers'} or reg['schema']!='EIGHT_GATE_SOURCE_V1' or set(reg['sources'])!=set(LOCAL):raise ValueError('gate source registry')
        if reg['helpers']!={k:dict(path=v[0],sha256=v[1]) for k,v in HELPERS.items()}:raise ValueError('fixed source-only helper set')
        sources={n:boot(HERE/n,h) for n,h in reg['sources'].items()}
        if sources['run_gate.py']!=Path(__file__).read_bytes():raise ValueError('executing gate source')
        s=types.ModuleType('gate_io');s.__file__=str(HERE/'production_support.py')
        exec(compile(sources['production_support.py'],s.__file__,'exec'),s.__dict__)
        live=s.MetadataBudget(384*len(regraw))
        apath=HERE/'ROOT_GATE_APPROVAL.json'
        ap=live.parse(s.read(apath,args.approval_sha256,ledger,2**20),ledger,'approval')
        gate_approval(ap,args.registry_sha256,reg['sources']['run_gate.py'])
        reviewpath=HERE/'ROOT_GATE_SOURCE_REVIEW.json'
        review=live.parse(s.read(reviewpath,ap['source_review_sha256'],ledger,2**20),ledger,'source review')
        if review.get('status')!='PASS_SOURCE_REVIEW' or review.get('registry_sha256')!=args.registry_sha256:raise ValueError('review binding')
        if platform.python_version()!='3.13.9' or any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')):raise ValueError('fixed runtime/threads')
        store=s.Store(HERE/ap['output'],deadline)
        metadata.update(source_pins=reg['sources'],helper_pins=reg['helpers'],runtime=platform.python_version())
        store.json('ATTEMPT.json',metadata)
        helper_raw={k:s.read(ROOT/v[0],v[1],ledger,2**20) for k,v in HELPERS.items()}
        modules={k:s.module(v,reg['sources'][k],k,HERE/k) for k,v in sources.items() if k not in ('run_gate.py','production_support.py')}
        helper_modules={k:s.module(helper_raw[k],v[1],k,ROOT/v[0]) for k,v in HELPERS.items() if k in ('old','fixtures','checker')}
        source_bytes=sum(map(len,sources.values()))+sum(map(len,helper_raw.values()))
        result=modules['cold_gate.py'].run_fixed(store=store,old=helper_modules['old'],fixtures=helper_modules['fixtures'],
                p=modules['prototype.py'],adapter=modules['adapter.py'],checker=helper_modules['checker'],
                source_bytes=source_bytes,hard_deadline=s.HardDeadline,synthetic_execution_authorized=True)
        for event in list(ledger):
            if 'path' in event:
                s.read(event['path'],event['sha256'],ledger,2**20)
        store.reauthenticate(ledger)
        store.json('ACCESS.json',ledger)
        result['registry_sha256']=args.registry_sha256
        result['producer_source_pins']={k:reg['sources'][k] for k in ('production_support.py','prototype.py','adapter.py')}
        store.json('GATE.json',result)
        complete=dict(metadata,status='COMPLETE',finish_utc=stamp(),elapsed_seconds=time.monotonic()-started,
                      outputs=dict(store.outputs),summary=result,live_metadata_charge=live.used)
        store.json('COMPLETE.json',complete)
        return complete
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL,0)
        if store is not None:
            s.retain_failure(store,metadata,ledger,started,exc,stamp())
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--registry-sha256',required=True);parser.add_argument('--approval-sha256',required=True)
    print(json.dumps(execute(parser.parse_args()),sort_keys=True))
