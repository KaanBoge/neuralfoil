"""Source-only two-phase entrypoint. No real approval/registry is supplied here.

All payload access follows authenticated source/approval/review gates. Capsule
extraction and model production have separate approvals, outputs and registries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ('production_support.py', 'prototype.py', 'capsule.py', 'adapter.py', 'run_phase.py')
MODEL = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'


def utc():
    return datetime.now(timezone.utc).isoformat()


def bootstrap(path, expected):
    p = Path(os.path.abspath(path))
    if any(x.is_symlink() for x in (p, *p.parents)) or p.stat().st_size > 2**20:
        raise ValueError('bootstrap path/size')
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('bootstrap identity')
    return raw


def approval(a, phase, regsha, entrysha):
    expected = dict(phase=phase, registry_sha256=regsha, entrypoint_sha256=entrysha,
                    output=phase+'_attempt_1', seconds=900, workers=1,
                    owned_cap=(256 if phase == 'capsule' else 128)*2**20,
                    output_cap=64*2**20, model_sha256=MODEL,
                    domain='FINITE_X62_V1', python='3.13.9', actual_execution_authorized=True)
    extra = {'source_review_sha256'} | ({'cold_gate_sha256','cold_gate_registry_sha256'} if phase == 'producer' else set())
    if type(a) != dict or set(a) != set(expected)|extra:
        raise ValueError('exact approval fields')
    for key, value in expected.items():
        if type(a[key]) is not type(value) or a[key] != value:
            raise ValueError('fixed approval value '+key)
    for key in extra:
        if type(a[key]) != str or len(a[key]) != 64 or any(c not in '0123456789abcdef' for c in a[key]):
            raise ValueError('approval evidence pin')


def execute(args):
    start = time.monotonic()
    deadline = start+900
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError('whole900second phase')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 900)
    store = None
    ledger = []
    metadata = dict(phase=args.phase, start_utc=utc(), registry_sha256=args.registry_sha256,
                    approval_sha256=args.approval_sha256)
    try:
        # Bootstrap only source/registry bytes, never model/certificate bytes.
        regpath = HERE/(args.phase.upper()+'_REGISTRY.json')
        raw = bootstrap(regpath, args.registry_sha256)
        # Before support-source discovery,384 bytes per input byte bounds the
        # lexical charge (containers/slots/strings); no uncharged bootstrap tree.
        bootstrap_charge=384*len(raw)
        if bootstrap_charge>8*2**20:raise MemoryError('bootstrap metadata admission')
        reg = json.loads(raw)
        if set(reg) != {'schema', 'phase', 'sources', 'helpers', 'inputs'} or reg['schema'] != 'EIGHT_SOURCE_REGISTRY_V1' or reg['phase'] != args.phase:
            raise ValueError('registry shape')
        if set(reg['sources']) != set(LOCAL):
            raise ValueError('exact local source closure')
        sources = {n: bootstrap(HERE/n, h) for n, h in reg['sources'].items()}
        if sources['run_phase.py'] != Path(__file__).read_bytes():
            raise ValueError('executing entry bytes')
        import types
        s = types.ModuleType('authenticated_eight_io')
        s.__file__ = str(HERE/'production_support.py')
        exec(compile(sources['production_support.py'], s.__file__, 'exec'), s.__dict__)
        live=s.MetadataBudget(bootstrap_charge)
        ledger.append(dict(operation='bootstrap_registry', path=str(regpath), sha256=args.registry_sha256, bytes=len(raw)))
        for n, data in sources.items():
            ledger.append(dict(operation='authenticated_source', name=n, sha256=s.sha(data), bytes=len(data)))
        apath = HERE/('ROOT_'+args.phase.upper()+'_APPROVAL.json')
        a = live.parse(s.read(apath, args.approval_sha256, ledger, 2**20), ledger, 'approval')
        approval(a, args.phase, args.registry_sha256, reg['sources']['run_phase.py'])
        if platform.python_version() != a['python'] or any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')):
            raise ValueError('fixed runtime/thread settings')
        rpath = HERE/('ROOT_'+args.phase.upper()+'_SOURCE_REVIEW.json')
        review = live.parse(s.read(rpath, a['source_review_sha256'], ledger, 2**20), ledger, 'review')
        if review.get('status') != 'PASS_SOURCE_REVIEW' or review.get('registry_sha256') != args.registry_sha256:
            raise ValueError('independent source review')
        if args.phase == 'producer':
            gatepath = HERE/'COLD_GATE_PASS.json'
            gate = live.parse(s.read(gatepath, a['cold_gate_sha256'], ledger, 2**20), ledger, 'fixed gate')
            if gate.get('status') != 'PASS_FIXED_315000_GATE' or gate.get('registry_sha256') != a['cold_gate_registry_sha256'] or gate.get('pair_classifications') != 315000:
                raise ValueError('fixed full-size gate')
            if gate.get('producer_source_pins') != {k:reg['sources'][k] for k in ('production_support.py','prototype.py','adapter.py')}:
                raise ValueError('same producer math/serialization as gate')
            for phase, cap in (('producer', 128*2**20), ('checker', 256*2**20)):
                g = gate[phase]
                if not 0 <= g['seconds'] <= 120 or not 0 <= g['owned_estimate'] <= cap or not 0 <= g['logical_output_bytes'] <= 64*2**20:
                    raise ValueError('unchanged fixed gate caps')
        store = s.Store(HERE/a['output'], deadline)
        metadata.update(runtime=dict(python=platform.python_version(), executable=os.path.realpath(os.sys.executable)),
                        source_pins=reg['sources'], helper_pins=reg['helpers'], limits={k:a[k] for k in ('seconds','owned_cap','output_cap','workers')})
        store.json('ATTEMPT.json', metadata)
        c = s.module(sources['capsule.py'], reg['sources']['capsule.py'], 'eight_capsule', HERE/'capsule.py')
        p = s.module(sources['prototype.py'], reg['sources']['prototype.py'], 'eight_prototype', HERE/'prototype.py')
        helper_key = 'old_parser' if args.phase == 'capsule' else 'old_inventory'
        expected_helper = c.PARSER if args.phase == 'capsule' else 'a445462d5faf314ecbd7ea06cb45feb8c26cf99de8d05d246d026b4bbea4b40e'
        if set(reg['helpers']) != {helper_key} or reg['helpers'][helper_key]['sha256'] != expected_helper:
            raise ValueError('fixed inherited helper')
        helper_entry = reg['helpers'][helper_key]
        helper_raw = s.read(ROOT/helper_entry['path'], expected_helper, ledger, 2**20)
        helper = s.module(helper_raw, expected_helper, 'eight_old_helper', ROOT/helper_entry['path'])
        source_bytes = sum(map(len, sources.values()))+len(helper_raw)
        if args.phase == 'capsule':
            if set(reg['inputs']) != set(c.FIXED) or any(reg['inputs'][k]['sha256'] != h for k,h in c.FIXED.items()):
                raise ValueError('fixed old proof registry')
            # Metadata first; certificate bytes are last, no model is permitted.
            refs = {}
            metadata_bytes = 0
            for key, entry in reg['inputs'].items():
                if key != 'old_certificate':
                    data = s.read(ROOT/entry['path'], entry['sha256'], ledger, 2**20)
                    metadata_bytes += len(data)
                    if metadata_bytes > 2**20:
                        raise MemoryError('1MiB aggregate predecessor metadata')
                    refs[key] = live.parse(data, ledger, key)
            c.authenticate_ancestry(refs)
            entry = reg['inputs']['old_certificate']
            cert_raw = s.read(ROOT/entry['path'], entry['sha256'], ledger, 64*2**20)
            # Existing lexical parser charges BEFORE parsed containers exist.
            cert, allocation = helper.parse_certificate(cert_raw, array_bytes=8*2**20, source_bytes=4*source_bytes)
            ledger.append(dict(operation='bounded_old_certificate_JSON_parse', sha256=c.CERT, bytes=len(cert_raw), lexical_allocation=allocation))
            value = c.extract(cert, refs, reg['sources']['capsule.py'], c.FIXED)
            del cert, cert_raw
            store.json('CAPSULE.json', value)
            result = dict(global_endpoints=100, inherited_proof=True, model_materializations=0,
                          lexical_allocation=allocation, owned_cap=256*2**20)
        else:
            if set(reg['inputs']) != {'capsule', 'capsule_complete', 'capsule_approval', 'capsule_registry', 'model'} or reg['inputs']['model']['sha256'] != MODEL:
                raise ValueError('producer finite inputs')
            refs = {}
            metadata_bytes = 0
            for key, entry in reg['inputs'].items():
                if key != 'model':
                    data = s.read(ROOT/entry['path'], entry['sha256'], ledger, 2**20)
                    metadata_bytes += len(data)
                    if metadata_bytes > 2**20:
                        raise MemoryError('1MiB aggregate capsule metadata')
                    refs[key] = live.parse(data, ledger, key)
            cc, ca, cr = (refs[k] for k in ('capsule_complete','capsule_approval','capsule_registry'))
            if (cc['status'] != 'COMPLETE' or cc['phase'] != 'capsule'
                    or cc['outputs'].get('CAPSULE.json') != reg['inputs']['capsule']['sha256']
                    or cc['approval_sha256'] != reg['inputs']['capsule_approval']['sha256']
                    or cc['registry_sha256'] != reg['inputs']['capsule_registry']['sha256']
                    or cr['sources']['capsule.py'] != reg['sources']['capsule.py']):
                raise ValueError('capsule completion/output lineage')
            approval(ca, 'capsule', reg['inputs']['capsule_registry']['sha256'], cr['sources']['run_phase.py'])
            # Reauthenticate every original capsule input (certificate streamed
            # below, not parsed) before accepting its inherited proof capsule.
            if set(cr['inputs']) != set(c.FIXED) or any(cr['inputs'][k]['sha256'] != h for k,h in c.FIXED.items()):
                raise ValueError('capsule fixed ancestry')
            for key, entry in cr['inputs'].items():
                path = s.safe(ROOT/entry['path'])
                h = hashlib.sha256()
                with path.open('rb') as f:
                    for chunk in iter(lambda:f.read(65536), b''):
                        store.check()
                        h.update(chunk)
                if h.hexdigest() != entry['sha256']:
                    raise ValueError('inherited proof bytes changed')
                ledger.append(dict(operation='streamed_inherited_authentication', path=str(path), sha256=entry['sha256']))
            chain = c.validate(refs['capsule'], reg['sources']['capsule.py'])
            entry = reg['inputs']['model']
            model_raw = s.read(ROOT/entry['path'], MODEL, ledger, 8*2**20)
            ad = s.module(sources['adapter.py'], reg['sources']['adapter.py'], 'eight_adapter', HERE/'adapter.py')
            expanded = ad.model_shape(model_raw, helper.MEMBERS)
            accounting = p.memory_plan(source_bytes, len(model_raw), expanded)
            arrays = ad.load_arrays(model_raw, helper.MEMBERS, MODEL, ledger)
            budget = p.Budget(max(0.001, deadline-time.monotonic()))
            result = ad.construct(arrays, refs['capsule'], chain, store, p, helper, budget, accounting)
            del arrays, model_raw
        # Reauthenticate source, approval, registry, review and ALL accessed paths.
        checked = set()
        for event in list(ledger):
            path, h = event.get('path'), event.get('sha256')
            if path is None or h is None or (path,h) in checked:
                continue
            checked.add((path,h))
            digest = hashlib.sha256()
            with s.safe(path).open('rb') as f:
                for chunk in iter(lambda:f.read(65536), b''):
                    store.check()
                    digest.update(chunk)
            if digest.hexdigest() != h:
                raise ValueError('end input authentication')
        for name, h in reg['sources'].items():
            s.read(HERE/name, h, ledger, 2**20)
        s.read(regpath, args.registry_sha256, ledger, 2**20)
        s.read(apath, args.approval_sha256, ledger, 2**20)
        store.reauthenticate(ledger)
        store.json('ACCESS.json', ledger)
        done = dict(metadata, status='COMPLETE', finish_utc=utc(), elapsed_seconds=time.monotonic()-start,
                    outputs=dict(store.outputs), summary=result,live_metadata_charge=live.used)
        store.json('COMPLETE.json', done)
        return done
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if store is not None:
            s.retain_failure(store,metadata,ledger,start,exc,utc())
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('capsule','producer'), required=True)
    parser.add_argument('--registry-sha256', required=True)
    parser.add_argument('--approval-sha256', required=True)
    print(json.dumps(execute(parser.parse_args()), sort_keys=True))
