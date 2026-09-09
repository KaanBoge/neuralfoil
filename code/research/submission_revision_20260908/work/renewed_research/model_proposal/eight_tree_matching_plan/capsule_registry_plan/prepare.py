"""Metadata-only registry preparer; actual invocation needs separate approval.

Never opens the certificate/model. The certificate pin is deferred to the
separately authorized capsule phase. No scientific module is imported.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent
ROOT = PLAN.parents[1]
SOURCES = {
    'production_support.py':'bd72a4c3deb81bbfb3bfe119003c16213c45eac1e307a296da186659a6545bbb',
    'prototype.py':'127e8de6cfed33f426eb77b5cb3b80d129653b6f3443de10dcb163bac358fc8b',
    'capsule.py':'d7e5e740d1bae420c0f60331be944971a441022fc5a06bf62e2338b79d64234a',
    'adapter.py':'fb0a015dd248a2dda10a4bb08261289fb115cd1e6a99fdef320b0963ecd54a00',
    'run_phase.py':'ebba473ad55adf6fda9599d3093e4a6404a55a4f77bc17417236aaaf09e25f7c',
}
P = 'model_proposal/four_tree_matching_plan/'
R = 'uncertainty_review/range_bound_feasibility/four_tree_matching/'
INPUTS = {
    'old_certificate':(P+'attempt_1/certificate.json','ace9cb3a22e094ea509e53a0258f4ed573097454e2b7a7716b4f1c7335dfcd6f'),
    'old_producer_complete':(P+'attempt_1/COMPLETE.json','dcb30c773b23f1a4dff91e5eb49058566793826aa9b699512b76390c5acc3704'),
    'old_producer_approval':(P+'ROOT_PRODUCER_APPROVAL.json','ce89fc902bd16dedbecbb70a5a7aa9b3fb6023dca0e1cd9b76ecfc89eefddcb7'),
    'old_producer_registry':(P+'REGISTRY_SOURCE_V1.json','6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc'),
    'old_replay_complete':(R+'attempt_1/COMPLETE.json','af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa'),
    'old_replay_result':(R+'attempt_1/REPLAY.json','ab0fc87f3a0f02eff3fff418309ecde9f416dde251e69ee41139c27a0d960f67'),
    'old_replay_approval':(R+'ROOT_REPLAY_APPROVAL.json','07f490cac240de2c4e4196c07d430e1bb05fab7379ff9a8fd6d990c9d4f0d2a8'),
    'old_checker_registry':(R+'CHECKER_SOURCE_REGISTRY_V1.json','2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26'),
}
HELPER = dict(path=R+'checker.py',sha256='ad4bbdf7b70fd862c959e3d916990890133f5ac4f9af714fb1e5ec6cc7706f1a')


def safe(path):
    p = Path(os.path.abspath(path))
    if any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('symlink')
    return p


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, expected, ledger):
    p = safe(path)
    if p.stat().st_size > 2**20:
        raise ValueError('metadata/source cap')
    raw = p.read_bytes()
    if len(raw)>2**20 or sha(raw) != expected:
        raise ValueError('authenticated buffer mismatch')
    ledger.append(dict(path=str(p),sha256=expected,bytes=len(raw),operation='authenticated_metadata_or_source_buffer'))
    return raw


def document(raw):
    # Fixed authenticated metadata only; conservative preparse bound.
    if len(raw)*384 > 8*2**20:
        raise MemoryError('metadata admission')
    return json.loads(raw)


def build(reader):
    """Injected finite reader permits synthetic-only tests, never reads proof."""
    for name,h in SOURCES.items():
        reader('source',name,h)
    reader('helper',HELPER['path'],HELPER['sha256'])
    metadata = {}
    total = 0
    for role,(path,h) in INPUTS.items():
        if role == 'old_certificate':
            continue
        raw = reader('metadata',path,h)
        total += 384*len(raw)
        if total>8*2**20:
            raise MemoryError('aggregate metadata admission')
        metadata[role] = document(raw)
    pc,rc = metadata['old_producer_complete'],metadata['old_replay_complete']
    if pc['status'] != 'COMPLETE' or rc['status'] != 'COMPLETE':
        raise ValueError('completed predecessor required')
    if pc['outputs']['certificate.json'] != INPUTS['old_certificate'][1] or rc['certificate_sha256'] != INPUTS['old_certificate'][1]:
        raise ValueError('certificate binding')
    if rc['producer_complete_sha256'] != INPUTS['old_producer_complete'][1] or rc['outputs']['REPLAY.json'] != INPUTS['old_replay_result'][1]:
        raise ValueError('replay predecessor binding')
    return dict(schema='EIGHT_SOURCE_REGISTRY_V1',phase='capsule',sources=dict(SOURCES),
                helpers={'old_parser':dict(HELPER)},
                inputs={k:dict(path=p,sha256=h) for k,(p,h) in INPUTS.items()})


def check_approval(a, entry_sha):
    expected = dict(phase='capsule_registry_metadata_preparation',entrypoint_sha256=entry_sha,
                    output='CAPSULE_REGISTRY.json',attempt='capsule_registry_preparation_attempt_1',
                    seconds=120,workers=1,output_cap=2**20,metadata_only=True,
                    actual_capsule_execution_authorized=False,preparation_authorized=True)
    if type(a) != dict or set(a) != set(expected):
        raise ValueError('exact approval fields')
    if any(type(a[k]) is not type(v) or a[k]!=v for k,v in expected.items()):
        raise ValueError('approval values')


def write(path, value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>65536:
        raise ValueError('output cap')
    with safe(path).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return sha(raw)


def execute(expected_approval):
    start=time.monotonic()
    previous=signal.getsignal(signal.SIGALRM)
    def timeout(*_):
        raise TimeoutError('120second metadata preparation')
    signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,120)
    ledger=[]
    attempt=None
    info=dict(start_utc=datetime.now(timezone.utc).isoformat(),approval_sha256=expected_approval)
    try:
        own=safe(__file__).read_bytes()
        ownsha=sha(own)
        a_path=PLAN/'ROOT_CAPSULE_REGISTRY_PREPARATION_APPROVAL.json'
        a=document(read(a_path,expected_approval,ledger))
        check_approval(a,ownsha)
        read(Path(__file__),ownsha,ledger)
        destination=safe(PLAN/a['output'])
        if destination.exists():
            raise FileExistsError('registry already exists')
        proposed=safe(PLAN/a['attempt'])
        proposed.mkdir(exist_ok=False)
        attempt=proposed
        write(attempt/'ATTEMPT.json',info)
        def reader(kind,path,h):
            return read((PLAN if kind=='source' else ROOT)/path,h,ledger)
        value=build(reader)
        for row in list(ledger):
            read(Path(row['path']),row['sha256'],[])
        # Fully serialize before exclusive publication; no retries or overwrites.
        h=write(destination,value)
        receipt=dict(info,status='COMPLETE_METADATA_PREPARATION',elapsed_seconds=time.monotonic()-start,
                     finish_utc=datetime.now(timezone.utc).isoformat(),registry_sha256=h,
                     source_sha256=ownsha,reads=ledger,certificate_bytes_read=0,model_materializations=0,
                     deferred_payload_authentication=['old_certificate'],actual_capsule_execution_authorized=False)
        write(attempt/'COMPLETE.json',receipt)
        return receipt
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL,0)
        if attempt is not None and attempt.exists():
            try:
                write(attempt/'FAILURE.json',dict(info,status='FAIL',error=repr(exc),reads=ledger,
                                               elapsed_seconds=time.monotonic()-start))
            except BaseException as secondary:
                print('Failure receipt error: '+repr(secondary)+'; primary: '+repr(exc),file=os.sys.stderr)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--approval-sha256',required=True)
    print(json.dumps(execute(p.parse_args().approval_sha256),sort_keys=True))
