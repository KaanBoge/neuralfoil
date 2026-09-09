"""Independent wrapper: authenticated checker, never eight-producer arithmetic."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import signal
import stat
import time
import types
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MODEL='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
OLD_CERT='ace9cb3a22e094ea509e53a0258f4ed573097454e2b7a7716b4f1c7335dfcd6f'
OLD_PC='dcb30c773b23f1a4dff91e5eb49058566793826aa9b699512b76390c5acc3704'
OLD_RC='af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa'
OLD_RR='ab0fc87f3a0f02eff3fff418309ecde9f416dde251e69ee41139c27a0d960f67'
OLD_PA='ce89fc902bd16dedbecbb70a5a7aa9b3fb6023dca0e1cd9b76ecfc89eefddcb7'
OLD_RA='07f490cac240de2c4e4196c07d430e1bb05fab7379ff9a8fd6d990c9d4f0d2a8'
OLD_PR='6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc'
OLD_CR='2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26'
FIXED=dict(model=MODEL,old_certificate=OLD_CERT,old_producer_complete=OLD_PC,
 old_replay_complete=OLD_RC,old_replay_result=OLD_RR,old_producer_approval=OLD_PA,
 old_replay_approval=OLD_RA,old_producer_registry=OLD_PR,old_checker_registry=OLD_CR)
HELPERS={
 'io':('model_proposal/eight_tree_matching_plan/production_support.py','bd72a4c3deb81bbfb3bfe119003c16213c45eac1e307a296da186659a6545bbb'),
 'checker':('uncertainty_review/range_bound_feasibility/eight_tree_matching/checker.py','bf9bf2afae7139eacbb2d0c35e09a3780a567e20cdb11216a525825c511ed792'),
 'old_checker':('uncertainty_review/range_bound_feasibility/four_tree_matching/checker.py','ad4bbdf7b70fd862c959e3d916990890133f5ac4f9af714fb1e5ec6cc7706f1a'),
 'primitive':('uncertainty_review/range_bound_feasibility/paired_checker.py','33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b')}
MEMBERS=('initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets',
         'binned_left_cat_bitsets','binned_left_cat_bitsets_offsets')


def utc():return datetime.now(timezone.utc).isoformat()


def strict_approval(a,regsha,entrysha):
    expected=dict(phase='eight_tree_independent_replay',registry_sha256=regsha,entrypoint_sha256=entrysha,
                  model_sha256=MODEL,old_certificate_sha256=OLD_CERT,old_replay_complete_sha256=OLD_RC,
                  domain='FINITE_X62_V1',seconds=900,workers=1,owned_cap=256*2**20,
                  output_cap=64*2**20,python='3.13.9',output='actual_replay_attempt_1',actual_execution_authorized=True)
    extra={'source_review_sha256','producer_complete_sha256','certificate_sha256'}
    if type(a)!=dict or set(a)!=set(expected)|extra:raise ValueError('exact replay approval')
    if any(type(a[k]) is not type(v) or a[k]!=v for k,v in expected.items()):raise ValueError('fixed replay scope')
    for k in extra:
        if type(a[k])!=str or len(a[k])!=64 or any(c not in '0123456789abcdef' for c in a[k]):raise ValueError('approval evidence pin')


def zip_headers(raw,ledger):
    """Validate archive and bounded NPY headers before array materialization."""
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=z.infolist()
        if len(entries)!=7 or set(z.namelist())!={k+'.npy' for k in MEMBERS}:raise ValueError('seven unique safe names')
        expanded=sum(e.file_size for e in entries)
        if expanded>4*2**20:raise MemoryError('expanded4MiB')
        for e in entries:
            if e.is_dir() or e.flag_bits&1 or stat.S_ISLNK(e.external_attr>>16):raise ValueError('archive entry semantics')
            with z.open(e) as f:
                version=np.lib.format.read_magic(f)
                if version not in ((1,0),(2,0)):raise ValueError('fixed NPY header version')
                size_bytes=2 if version==(1,0) else 4
                length_raw=f.read(size_bytes)
                if len(length_raw)!=size_bytes or int.from_bytes(length_raw,'little')>4096:
                    raise ValueError('header length before header allocation')
                f.seek(8) # after magic/version, before the bounded length field
                if version==(1,0):shape,order,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=4096)
                else:shape,order,dtype=np.lib.format.read_array_header_2_0(f,max_header_size=4096)
                if dtype.hasobject or len(shape)>2 or any(type(n)!=int or n<0 or n>11600 for n in shape):raise ValueError('safe NPY dtype/shape')
                elements=1
                for n in shape:elements*=n
                if elements*dtype.itemsize+f.tell()!=e.file_size:raise ValueError('exact NPY payload size')
                ledger.append(dict(operation='NPY_header_validation',member=e.filename,shape=list(shape),dtype=str(dtype),expanded_bytes=e.file_size))
        return expanded


def old_chain(refs):
    pc,rc,rr,pa,ra=(refs[k] for k in ('old_producer_complete','old_replay_complete','old_replay_result','old_producer_approval','old_replay_approval'))
    if (pc['status']!='COMPLETE' or rc['status']!='COMPLETE' or pc['model_sha256']!=MODEL or rc['model_sha256']!=MODEL
        or pc['registry_sha256']!=OLD_PR or rc['checker_registry_sha256']!=OLD_CR or rc['producer_registry_sha256']!=OLD_PR
        or pc['approval_sha256']!=OLD_PA or rc['approval_sha256']!=OLD_RA
        or pc['outputs']['certificate.json']!=OLD_CERT or rc['outputs']['REPLAY.json']!=OLD_RR
        or rc['producer_complete_sha256']!=OLD_PC or rc['certificate_sha256']!=OLD_CERT):raise ValueError('old completion identity')
    if (pa['real_execution_authorized'] is not True or ra['real_execution_authorized'] is not True
        or pa['registry_sha256']!=OLD_PR or ra['producer_registry_sha256']!=OLD_PR
        or ra['checker_registry_sha256']!=OLD_CR or ra['producer_complete_sha256']!=OLD_PC
        or ra['certificate_sha256']!=OLD_CERT or rr['status']!='PASS_INDEPENDENT_FOUR_TREE_MATCHING_REPLAY'
        or rr['model_sha256']!=MODEL or rr['final']!=rc['summary']['final']):raise ValueError('old proof approval/result')


def execute(args):
    started=time.monotonic();deadline=started+900;handler=signal.getsignal(signal.SIGALRM)
    def expired(*_):raise TimeoutError('whole900second independent replay')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    store=None;ledger=[]
    metadata=dict(phase='eight_tree_independent_replay',start_utc=utc(),registry_sha256=args.registry_sha256,approval_sha256=args.approval_sha256)
    try:
        def boot(path,pin):
            path=Path(os.path.abspath(path))
            if any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size>2**20:raise ValueError('source bootstrap')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('bootstrap hash')
            ledger.append(dict(operation='authenticated_source_bytes',path=str(path),sha256=pin,bytes=len(raw)));return raw
        regraw=boot(HERE/'REGISTRY.json',args.registry_sha256)
        if 384*len(regraw)>8*2**20:raise MemoryError('registry metadata admission')
        reg=json.loads(regraw)
        if set(reg)!={'schema','sources','helpers','inputs'} or reg['schema']!='EIGHT_REPLAY_SOURCE_V1' or set(reg['sources'])!={'replay.py'}:raise ValueError('exact source registry')
        if reg['helpers']!={k:dict(path=v[0],sha256=v[1]) for k,v in HELPERS.items()}:raise ValueError('fixed independent sources')
        source=boot(HERE/'replay.py',reg['sources']['replay.py'])
        if source!=Path(__file__).read_bytes():raise ValueError('executing source')
        helper_raw={k:boot(ROOT/v[0],v[1]) for k,v in HELPERS.items()}
        s=types.ModuleType('independent_eight_io');s.__file__=str(ROOT/HELPERS['io'][0]);exec(compile(helper_raw['io'],s.__file__,'exec'),s.__dict__)
        live=s.MetadataBudget(384*len(regraw))
        a=live.parse(s.read(HERE/'ROOT_APPROVAL.json',args.approval_sha256,ledger,2**20),ledger,'approval')
        strict_approval(a,args.registry_sha256,reg['sources']['replay.py'])
        review=live.parse(s.read(HERE/'ROOT_SOURCE_REVIEW.json',a['source_review_sha256'],ledger,2**20),ledger,'source review')
        if review.get('status')!='PASS_SOURCE_REVIEW' or review.get('registry_sha256')!=args.registry_sha256:raise ValueError('independent review gate')
        if platform.python_version()!='3.13.9' or any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')):raise ValueError('fixed runtime threads')
        store=s.Store(HERE/a['output'],deadline)
        metadata.update(source_pins=reg['sources'],helper_pins=reg['helpers'],model_sha256=MODEL,
                        certificate_sha256=a['certificate_sha256'],producer_complete_sha256=a['producer_complete_sha256'],runtime=platform.python_version())
        store.json('ATTEMPT.json',metadata)
        candidates={'certificate','producer_complete','producer_approval','producer_registry'}
        if set(reg['inputs'])!=set(FIXED)|candidates or any(reg['inputs'][k]['sha256']!=h for k,h in FIXED.items()):raise ValueError('finite fixed input roles')
        if reg['inputs']['certificate']['sha256']!=a['certificate_sha256'] or reg['inputs']['producer_complete']['sha256']!=a['producer_complete_sha256']:raise ValueError('candidate approval pins')
        def meta(key,entry):return live.parse(s.read(ROOT/entry['path'],entry['sha256'],ledger,2**20),ledger,key)
        refs={k:meta(k,v) for k,v in reg['inputs'].items() if k not in ('model','old_certificate','certificate')}
        old_chain(refs)
        pc,pa,pr=(refs[k] for k in ('producer_complete','producer_approval','producer_registry'))
        if (pc['status']!='COMPLETE' or pc['phase']!='producer' or pc['registry_sha256']!=reg['inputs']['producer_registry']['sha256']
            or pc['approval_sha256']!=reg['inputs']['producer_approval']['sha256'] or pc['outputs']['certificate.jsonl']!=a['certificate_sha256']
            or pa['actual_execution_authorized'] is not True or pa['phase']!='producer' or pa['model_sha256']!=MODEL
            or pa['registry_sha256']!=pc['registry_sha256']):raise ValueError('completed authorized producer')
        # Authenticate all producer source and capsule lineage metadata. These
        # are bytes/provenance only; NO producer source is imported/executed.
        producer_base=s.safe(ROOT/reg['inputs']['producer_registry']['path']).parent
        for name,h in pr['sources'].items():
            if Path(name).name!=name:raise ValueError('producer source names')
            s.read(producer_base/name,h,ledger,2**20)
        for key in ('capsule','capsule_complete','capsule_approval','capsule_registry'):
            refs[key]=meta(key,pr['inputs'][key])
        cc=refs['capsule_complete']
        if (cc['status']!='COMPLETE' or cc['phase']!='capsule'
            or cc['outputs']['CAPSULE.json']!=pr['inputs']['capsule']['sha256']
            or cc['approval_sha256']!=pr['inputs']['capsule_approval']['sha256']
            or cc['registry_sha256']!=pr['inputs']['capsule_registry']['sha256']
            or refs['capsule_approval']['actual_execution_authorized'] is not True):raise ValueError('capsule completed ancestry')
        def streamed(entry,limit):
            path=s.safe(ROOT/entry['path']);size=path.stat().st_size
            if size>limit:raise MemoryError('streamed input cap')
            h=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(65536),b''):store.check();h.update(chunk)
            if h.hexdigest()!=entry['sha256']:raise ValueError('streamed exact input')
            ledger.append(dict(operation='streamed_input_authentication',path=str(path),sha256=h.hexdigest(),bytes=size));return path,size
        certpath,certsize=streamed(reg['inputs']['certificate'],63*2**20)
        oldpath,oldsize=streamed(reg['inputs']['old_certificate'],64*2**20)
        checker=s.module(helper_raw['checker'],HELPERS['checker'][1],'root_independent_eight',ROOT/HELPERS['checker'][0])
        source_bytes=len(source)+sum(map(len,helper_raw.values()))
        # Full declared expansion reserve BEFORE raw model/old certificate load.
        # The checker retains raw model bytes and parsed metadata outside its
        # own model-array argument. Charge them as additional source bytes:
        # fourfold in eight phase, at least once in inherited old-four parser.
        admission=checker.owned_estimate(4*2**20,source_bytes+16*2**20,oldsize,2**20)
        if admission>256*2**20:raise MemoryError('prearray wrapper owned admission')
        model_raw=s.read(ROOT/reg['inputs']['model']['path'],MODEL,ledger,8*2**20)
        expanded=zip_headers(model_raw,ledger)
        import numpy as np
        with np.load(io.BytesIO(model_raw),allow_pickle=False) as z:
            arrays={}
            for key in MEMBERS:
                arrays[key]=z[key]
                ledger.append(dict(operation='NPZ_materialization',member=key,shape=list(arrays[key].shape),dtype=str(arrays[key].dtype),model_sha256=MODEL))
        oldraw=s.read(oldpath,OLD_CERT,ledger,64*2**20)
        expected=dict(model_sha256=MODEL,old4_certificate_sha256=OLD_CERT,old4_replay_complete_sha256=OLD_RC)
        charged_sources=source_bytes+8*2**20+len(model_raw)
        with certpath.open('rb') as f:result=checker.check_stream(f,arrays,oldraw,expected=expected,source_bytes=charged_sources,deadline=deadline)
        if result['stream_sha256']!=a['certificate_sha256'] or result['counts']!=pc['summary']['counts'] or result['final']!=pc['summary']['final']:raise ValueError('independent full candidate parity')
        del arrays,model_raw,oldraw
        # Reauthenticate every actual input/source path using bounded chunks.
        for event in list(ledger):
            if 'path' in event:streamed(dict(path=event['path'],sha256=event['sha256']),64*2**20)
        store.json('REPLAY.json',result);store.reauthenticate(ledger);store.json('ACCESS.json',ledger)
        complete=dict(metadata,status='COMPLETE',finish_utc=utc(),elapsed_seconds=time.monotonic()-started,
                      outputs=dict(store.outputs),summary=result,wrapper_prearray_owned_admission=admission,
                      expanded_model_bytes=expanded,live_metadata_charge=live.used)
        store.json('COMPLETE.json',complete);return complete
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL,0)
        if store is not None:s.retain_failure(store,metadata,ledger,started,exc,utc())
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--registry-sha256',required=True);ap.add_argument('--approval-sha256',required=True)
    print(json.dumps(execute(ap.parse_args()),sort_keys=True))
