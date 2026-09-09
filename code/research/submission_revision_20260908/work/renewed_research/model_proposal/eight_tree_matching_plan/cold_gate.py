"""Fixed full-size gate source only. Never called by ordinary test discovery.

Requires a separately reviewed/authenticated outer gate wrapper. All injected
modules must be executed from pinned sources before calling this function.
This source defines fixture and timing scope, but grants no execution authority.
"""
from fractions import Fraction as F
import hashlib
import json
import os
import time

FIXTURE_SHA = '76d0da75d8f2c4893e9eaa2ee57c50366050d77d33c1eab9bbb20819620d8228'
DECLARATION = b'EIGHT_FIXED_400x15_DEPTH14_315000_D_V1'


def stream_old_object(store, value):
    """Large old synthetic object streamed without a full JSON text copy."""
    path = store.path/'old_four_synthetic.json'
    store.check()
    h = hashlib.sha256()
    with path.open('xb') as f:
        buf=bytearray()
        for token in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(value):
            # Old producer has finite admitted values; tokens<=1027 characters.
            raw=token.encode('ascii')
            if len(raw)>16384:raise ValueError('fixed fixture token')
            if len(buf)+len(raw)>16384:
                store.check(len(buf));f.write(buf);f.flush();h.update(buf);buf.clear()
            buf.extend(raw)
        if buf:
            store.check(len(buf));f.write(buf);f.flush();h.update(buf)
        os.fsync(f.fileno())
    store.outputs[path.name]=h.hexdigest()
    return h.hexdigest()


def run_fixed(*, store, old, fixtures, p, adapter, checker, source_bytes,
              hard_deadline, synthetic_execution_authorized=False):
    if synthetic_execution_authorized is not True:
        raise PermissionError('separate full-size synthetic approval required')
    # The sole predeclared 400x15 chain fixture from the pinned prior source.
    # No actual model is read. Source identity must be checked by outer wrapper.
    synthetic_model=hashlib.sha256(DECLARATION).hexdigest()
    # Preparation separately admitted under256MiB, not called producer128MiB.
    before=time.monotonic()
    with hard_deadline(120):
        if old.memory_plan(4*2**20,0,source_bytes)['estimated_owned_bytes']+64*2**20>256*2**20:
            raise MemoryError('pre-fixture allocation admission256MiB')
        arrays=fixtures.performance_arrays()
        array_bytes=sum(a.nbytes for a in arrays.values())
        prep_estimate=old.memory_plan(array_bytes,0,source_bytes)['estimated_owned_bytes']+64*2**20
        if prep_estimate>256*2**20:raise MemoryError('old synthetic precursor256MiB')
        old_cert=old.construct(arrays,old.Budget(120),model_sha=synthetic_model,source_bytes=source_bytes)
        old_sha=stream_old_object(store,old_cert)
        chain=[tuple(F(int(v['numerator'],16),int(v['denominator'],16)) for v in b['outgoing']) for b in old_cert['blocks']]
        capsule=dict(model_sha256=synthetic_model,initial=old_cert['initial'],
                     certificate_sha256=old_sha,replay_complete_sha256=hashlib.sha256(b'synthetic inherited proof').hexdigest(),
                     final=old_cert['final'])
        del old_cert
    prep_seconds=time.monotonic()-before
    if prep_seconds>120:raise TimeoutError('fixed preparation120s')
    producer_start=time.monotonic()
    with hard_deadline(120):
        accounting=p.memory_plan(source_bytes,0,array_bytes)
        result=adapter.construct(arrays,capsule,chain,store,p,old,p.Budget(120),accounting)
    producer_seconds=time.monotonic()-producer_start
    if producer_seconds>120 or result['counts']['pair_classifications']!=315000:
        raise ValueError('fixed producer cardinality/time gate')
    # old raw bytes only come live after producer scratch/path inventory exits.
    expected=dict(model_sha256=synthetic_model,old4_certificate_sha256=old_sha,
                  old4_replay_complete_sha256=capsule['replay_complete_sha256'])
    check_start=time.monotonic()
    with hard_deadline(120):
        old_path=store.path/'old_four_synthetic.json'
        if old_path.stat().st_size>64*2**20:raise MemoryError('old raw cap')
        old_raw=old_path.read_bytes()
        if hashlib.sha256(old_raw).hexdigest()!=old_sha:raise ValueError('old synthetic bytes changed')
        with (store.path/'certificate.jsonl').open('rb') as stream:
            qa=checker.check_stream(stream,arrays,old_raw,expected=expected,
                                    source_bytes=source_bytes,deadline=check_start+120)
    checker_seconds=time.monotonic()-check_start
    if checker_seconds>120 or qa['counts']!=result['counts'] or qa['final']!=result['final']:
        raise ValueError('fixed independent gate parity/time')
    if qa['estimated_owned_bytes']>256*2**20:raise MemoryError('checker256MiB')
    return dict(status='PASS_FIXED_315000_GATE',pair_classifications=315000,
                preparation=dict(seconds=prep_seconds,owned_estimate=prep_estimate),
                producer=dict(seconds=producer_seconds,owned_estimate=accounting['estimate'],logical_output_bytes=store.used()),
                checker=dict(seconds=checker_seconds,owned_estimate=qa['estimated_owned_bytes'],logical_output_bytes=store.used()),
                independent_result=qa, actual_model_materializations=0)
