"""Source-only independent actual replay entry; explicit root approval required.

No producer scientific functions are used. Shared streaming publication code is
not part of the independently reconstructed mathematical certificate.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import signal
import time
import types
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRODUCER = ROOT / 'model_proposal/four_tree_matching_plan'
MODEL = ROOT / 'independent_environment/bounds_extraction/arrays/tree_31_capped.npz'
MODEL_SHA = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
PHASE = 'four_tree_matching_replay'
SOURCE_PATHS = {
    'checker': 'uncertainty_review/range_bound_feasibility/four_tree_matching/checker.py',
    'entry': 'uncertainty_review/range_bound_feasibility/four_tree_matching/replay.py',
    'primitive': 'uncertainty_review/range_bound_feasibility/paired_checker.py',
    'io': 'model_proposal/four_tree_matching_plan/io_support.py',
}
MEMBERS = ('initial', 'nodes', 'nodes_offsets', 'raw_left_cat_bitsets',
           'raw_left_cat_bitsets_offsets', 'binned_left_cat_bitsets',
           'binned_left_cat_bitsets_offsets')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def module(raw, name, path):
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), mod.__dict__)
    return mod


def exact(actual, expected):
    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError('exact scoped metadata')


def strict_approval(ap, checker_registry, producer_registry):
    fixed = {'phase': PHASE, 'checker_registry_sha256': checker_registry,
             'producer_registry_sha256': producer_registry, 'model_sha256': MODEL_SHA,
             'domain': 'FINITE_X62_V1', 'seconds': 900, 'workers': 1,
             'owned_cap': 256*2**20, 'output_cap': 64*2**20,
             'real_execution_authorized': True, 'output': 'attempt_1'}
    pins = {'producer_complete_sha256', 'producer_approval_sha256',
            'certificate_sha256', 'source_review_sha256', 'synthetic_gate_sha256'}
    if type(ap) is not dict or set(ap) != set(fixed) | pins:
        raise ValueError('approval fields')
    exact({k: ap[k] for k in fixed}, fixed)
    for k in pins:
        if type(ap[k]) is not str or len(ap[k]) != 64 or any(c not in '0123456789abcdef' for c in ap[k]):
            raise ValueError('approval SHA')


def independent_arrays(raw, ledger):
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        items = z.infolist()
        if len(items) != 7 or set(z.namelist()) != {k+'.npy' for k in MEMBERS}:
            raise ValueError('exact independent seven-member intake')
        if any(v.flag_bits & 1 for v in items) or sum(v.file_size for v in items) > 4*2**20:
            raise ValueError('bounded nonencrypted model payload')
    arrays = {}
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        for key in MEMBERS:
            value = z[key]
            if value.dtype.hasobject:
                raise ValueError('object dtype')
            arrays[key] = value
            ledger.append({'operation': 'independent NPZ materialization', 'member': key,
                           'model_sha256': MODEL_SHA, 'shape': list(value.shape),
                           'dtype': str(value.dtype)})
    return arrays


def resource_gate(gate):
    for name, cap in (('producer', 128*2**20), ('checker', 256*2**20)):
        v = gate[name]
        elapsed = v['seconds']
        if (type(elapsed) not in (int, float) or not math.isfinite(elapsed)
                or not 0 <= elapsed <= 120):
            raise ValueError('fixed cold phase deadline')
        for key, limit in (('owned_estimate', cap), ('logical_output_bytes', 64*2**20)):
            if type(v[key]) is not int or not 0 <= v[key] <= limit:
                raise ValueError('fixed cold phase resource limit')


def reauthenticate(path, pin, limit, ledger, deadline):
    """Hash-only completion check: no second full scientific input buffer."""
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('reauthentication path')
    if path.stat().st_size > limit:
        raise ValueError('reauthentication input cap')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as source:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('reauthentication deadline')
            chunk = source.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError('reauthentication growing input')
            digest.update(chunk)
    if digest.hexdigest() != pin:
        raise ValueError('reauthentication exact SHA')
    ledger.append({'operation': 'streamed input reauthentication', 'path': str(path),
                   'sha256': pin, 'bytes': size, 'maximum_chunk_bytes': 65536})


def reference_equal(result, refs):
    def fraction(v):
        return F(int(v['numerator'], 16), int(v['denominator'], 16))
    if refs['manifest']['files'].get('arrays/tree_31_capped.npz') != MODEL_SHA:
        raise ValueError('original manifest model')
    rows = [v for v in refs['stage0']['records'] if v['context'] == 'final']
    if len(rows) != 1 or refs['stage0']['accessed_tree_sha256'].get('arrays/tree_31_capped.npz') != MODEL_SHA:
        raise ValueError('original Stage0 model identity')
    for k in ('lower', 'upper'):
        v = rows[0]['range'][k]
        if fraction(result['stage0'][k]) != F(int(v['numerator']), int(v['denominator'])):
            raise ValueError('independent original Stage0 arithmetic')
    v = rows[0]['B_structural']
    if fraction(result['stage0']['B']) != F(int(v['numerator']), int(v['denominator'])):
        raise ValueError('independent original Stage0 B')
    old = refs['adjacent_replay']
    if old.get('status') != 'PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY' or old.get('model_sha256') != MODEL_SHA:
        raise ValueError('old adjacent replay identity')
    for k in ('lower', 'upper', 'B'):
        if fraction(result['original_adjacent'][k]) != fraction(old['summary']['D'][k]):
            raise ValueError('independent old D equality')


def execute(args):
    early = []
    def boot(path, pin):
        path = Path(os.path.abspath(path))
        if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > 2**20:
            raise ValueError('bootstrap path or size')
        raw = path.read_bytes()
        if sha(raw) != pin:
            raise ValueError('bootstrap exact SHA')
        early.append({'operation': 'authenticated bytes', 'path': str(path), 'sha256': pin, 'bytes': len(raw)})
        return raw
    regpath = HERE / 'CHECKER_SOURCE_REGISTRY_V1.json'
    reg = json.loads(boot(regpath, args.registry_sha256))
    if (type(reg) is not dict or set(reg) != {'schema', 'model_sha256', 'sources', 'producer_registry_sha256'}
            or reg['schema'] != 'FOUR_TREE_CHECKER_SOURCE_REGISTRY_V1' or reg['model_sha256'] != MODEL_SHA
            or set(reg['sources']) != set(SOURCE_PATHS)):
        raise ValueError('checker source registry schema')
    sources = {}
    for role, path in SOURCE_PATHS.items():
        entry = reg['sources'][role]
        if set(entry) != {'path', 'sha256'} or entry['path'] != path:
            raise ValueError('fixed checker source path')
        sources[role] = boot(ROOT/path, entry['sha256'])
    if sources['entry'] != Path(__file__).read_bytes():
        raise ValueError('executing entry byte identity')
    s = module(sources['io'], 'four_tree_replay_streaming_io', ROOT/SOURCE_PATHS['io'])
    appath = HERE/'ROOT_REPLAY_APPROVAL.json'
    ap = s.parse(s.pinned(appath, args.approval_sha256, early), early, 'root independent replay approval')
    strict_approval(ap, args.registry_sha256, reg['producer_registry_sha256'])
    producer_registry_path = PRODUCER/'REGISTRY_SOURCE_V1.json'
    preg = s.parse(s.pinned(producer_registry_path, reg['producer_registry_sha256'], early), early, 'producer registry')
    for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        if os.environ.get(k) != '1':
            raise ValueError('one-worker thread environment')
    start = time.monotonic()
    deadline = start+900
    store = s.Store(HERE/'attempt_1', deadline)
    ledger = list(early)
    inputs = [(regpath, args.registry_sha256, 2**20), (appath, args.approval_sha256, 2**20),
              (producer_registry_path, reg['producer_registry_sha256'], 2**20)]
    metadata = {'phase': PHASE, 'checker_registry_sha256': args.registry_sha256,
                'producer_registry_sha256': reg['producer_registry_sha256'],
                'approval_sha256': args.approval_sha256, 'model_sha256': MODEL_SHA,
                'start_utc': utc(), 'runtime': {'python': platform.python_version(), 'platform': platform.platform()},
                'limits': {k: ap[k] for k in ('seconds', 'workers', 'owned_cap', 'output_cap')}}
    old_handler = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError('900-second independent replay guard')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 900)
    def read(path, pin, limit=2**20):
        inputs.append((path, pin, limit))
        return s.pinned(path, pin, ledger, limit)
    try:
        store.write_json('ATTEMPT.json', metadata)
        checker = module(sources['checker'], 'four_tree_independent_checker', ROOT/SOURCE_PATHS['checker'])
        if checker.PRIMITIVE_SHA != reg['sources']['primitive']['sha256']:
            raise ValueError('independent primitive pin')
        review = s.parse(read(PRODUCER/'ROOT_SOURCE_REVIEW.json', ap['source_review_sha256']), ledger, 'source review')
        gate = s.parse(read(PRODUCER/'COLD_GATE_PASS.json', ap['synthetic_gate_sha256']), ledger, 'cold gate')
        if (review.get('status') != 'PASS_SOURCE_REVIEW' or review.get('registry_sha256') != reg['producer_registry_sha256']
                or review.get('checker_registry_sha256') != args.registry_sha256
                or gate.get('status') != 'PASS_FIXED_135000_GATE'
                or gate.get('registry_sha256') != reg['producer_registry_sha256']
                or gate.get('checker_registry_sha256') != args.registry_sha256
                or gate.get('pair_classifications') != 135000):
            raise ValueError('review and fixed synthetic scope')
        resource_gate(gate)
        complete = s.parse(read(PRODUCER/'attempt_1/COMPLETE.json', ap['producer_complete_sha256']), ledger, 'producer completion')
        pap = s.parse(read(PRODUCER/'ROOT_PRODUCER_APPROVAL.json', ap['producer_approval_sha256']), ledger, 'producer approval')
        if ((PRODUCER/'attempt_1/FAILURE.json').exists()
                or complete.get('status') != 'COMPLETE' or complete.get('phase') != 'four_tree_matching_produce'
                or complete.get('registry_sha256') != reg['producer_registry_sha256']
                or complete.get('model_sha256') != MODEL_SHA
                or complete.get('approval_sha256') != ap['producer_approval_sha256']
                or complete['outputs'].get('certificate.json') != ap['certificate_sha256']
                or pap.get('real_execution_authorized') is not True
                or pap.get('registry_sha256') != reg['producer_registry_sha256']
                or pap.get('source_review_sha256') != ap['source_review_sha256']
                or pap.get('synthetic_gate_sha256') != ap['synthetic_gate_sha256']):
            raise ValueError('completed authorized producer chain')
        refs = {}
        for role in ('manifest', 'stage0', 'adjacent_replay'):
            entry = preg['predecessors'][role]
            refs[role] = s.parse(read(ROOT/entry['path'], entry['sha256']), ledger, role)
        certpath = PRODUCER/'attempt_1/certificate.json'
        source_bytes = sum(map(len, sources.values()))
        compressed_size = MODEL.stat().st_size
        certificate_size = certpath.stat().st_size
        if compressed_size > 8*2**20 or certificate_size > checker.INPUT_CAP:
            raise MemoryError('bounded serialized inputs')
        # Admission before either scientific serialized payload is materialized.
        estimate = checker.owned_estimate(4*2**20, source_bytes+compressed_size, certificate_size)
        if estimate > checker.MEMORY_CAP:
            raise MemoryError('pre-input checker owned-memory limit')
        raw_cert = read(certpath, ap['certificate_sha256'], checker.INPUT_CAP)
        certificate, allocation = checker.parse_certificate(raw_cert, array_bytes=4*2**20,
                                                             source_bytes=source_bytes+compressed_size)
        admitted_peak = max(estimate, checker.owned_estimate(4*2**20, source_bytes+compressed_size,
                                                            certificate_size, allocation))
        ledger.append({'operation': 'bounded certificate JSON parse', 'sha256': ap['certificate_sha256'],
                       'bytes': len(raw_cert), 'lexical_allocation_estimate': allocation})
        raw_model = read(MODEL, MODEL_SHA, 8*2**20)
        arrays = independent_arrays(raw_model, ledger)
        result = checker.check(certificate, arrays, deadline, expected_model_sha=MODEL_SHA,
                               source_bytes=source_bytes+len(raw_model), input_bytes=len(raw_cert),
                               parsed_bytes=allocation)
        reference_equal(result, refs)
        store.write_json('REPLAY.json', result)
        for path, pin, limit in inputs:
            reauthenticate(path, pin, limit, ledger, deadline)
        for role, entry in reg['sources'].items():
            reauthenticate(ROOT/entry['path'], entry['sha256'], 2**20, ledger, deadline)
        if (PRODUCER/'attempt_1/FAILURE.json').exists():
            raise ValueError('producer failure appeared')
        store.verify_outputs(ledger)
        store.write_json('ACCESS.json', ledger)
        receipt = dict(metadata, status='COMPLETE', finish_utc=utc(),
                       elapsed_seconds=time.monotonic()-start,
                       producer_complete_sha256=ap['producer_complete_sha256'],
                       certificate_sha256=ap['certificate_sha256'], outputs=dict(store.outputs),
                       summary={'counts': result['counts'], 'stage0': result['stage0'],
                                'original_adjacent': result['original_adjacent'], 'final': result['final'],
                                'checker_accounting': result['checker_accounting'],
                                'wrapper_owned_admission_peak': admitted_peak,
                                'features_targets_calibration_loaded': 0, 'fits': 0, 'R_used': False,
                                'model_materializations': 1})
        store.write_json('COMPLETE.json', receipt)
        return receipt
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        store.write_json('FAILURE.json', dict(metadata, status='NO_NEW_CERTIFICATE',
                         finish_utc=utc(), elapsed_seconds=time.monotonic()-start,
                         error=repr(exc)[:4096], accepted_outputs=dict(store.outputs),
                         last_access=ledger[-20:]), emergency=True)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry-sha256', required=True)
    parser.add_argument('--approval-sha256', required=True)
    print(json.dumps(execute(parser.parse_args()), sort_keys=True))
