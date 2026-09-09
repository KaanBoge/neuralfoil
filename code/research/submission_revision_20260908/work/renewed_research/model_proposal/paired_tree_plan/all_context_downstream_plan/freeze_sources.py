"""Explicit future registry freeze; missing replay receipt makes this fail closed.

Do not invoke until root supplies and approves the exact inherited input specification.
Reads code/provenance only, never scientific archive members. Exclusive output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import run

FILES = ['run.py', 'storage.py', 'adapter.py', 'study.py', 'test_storage.py',
         'test_successor.py', 'freeze_sources.py', 'PLAN.md', 'HANDOFF.md']
PROVENANCE = ['synthetic_failure_1/RESULT.json', 'synthetic_failure_1/storage.py',
              'source_review_failure_2/RESULT.json', 'source_review_failure_2/adapter.py',
              'source_review_failure_2/run.py', 'source_review_failure_2/freeze_sources.py',
              'source_review_failure_2/test_successor.py',
              'TEST_RESULT.json', 'INHERITED_INPUTS.json', 'SOURCE_DIFF.patch']


def freeze(spec_path, spec_sha):
    inherited = json.loads(run.raw(spec_path, spec_sha))
    required = {'registry_sha256', 'producer_sha256', 'replay_sha256',
                'producer_approval_path', 'producer_approval_sha256',
                'replay_approval_path', 'replay_approval_sha256'}
    if set(inherited) != required:
        raise ValueError('exact inherited specification required')
    buffers = {name: (run.HERE / name).read_bytes() for name in FILES}
    pins = {name: hashlib.sha256(raw).hexdigest() for name, raw in buffers.items()}
    provenance = {name: hashlib.sha256((run.HERE / name).read_bytes()).hexdigest() for name in PROVENANCE}
    legacy = json.loads(run.raw(run.LEGACY / 'REGISTRY_v3.json', run.OLD_REGISTRY))
    with run.loaded({name: (path, raw) for name, path, raw in [
        ('legacy_adapter', run.LEGACY / 'adapter.py', run.raw(run.LEGACY / 'adapter.py', run.OLD_ADAPTER)),
        ('storage', run.HERE / 'storage.py', buffers['storage.py']),
        ('adapter', run.HERE / 'adapter.py', buffers['adapter.py'])]
    }) as ms:
        a = ms['adapter']
        for name in ('producer_approval_path', 'replay_approval_path'):
            p = Path(inherited[name])
            if p.is_absolute() or '..' in p.parts:
                raise ValueError('relative inherited path')
        reg = dict(sources=pins, provenance=provenance, entrypoint_sha256=pins['run.py'], inherited=inherited,
                   inherited_spec_sha256=spec_sha, external_sources=legacy['external_sources'],
                   phases=list(a.PHASES), contexts=a.CONTEXTS,
                   output_roots=[str(p.relative_to(a.ROOT)) for p in a.roots()],
                   logical_cap=ms['storage'].CAP, failure_reserve=ms['storage'].RESERVE,
                   actual_phase_authorized=False)
        raw = json.dumps(reg, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        h = hashlib.sha256(raw).hexdigest()
        a.bind(reg, h, {run.HERE / n: p for n, p in pins.items()})
        ledger = []
        a.certificate_chain('certificates_replay', inherited['replay_sha256'], h, ledger)
        witness = json.dumps({'status': 'METADATA_CHAIN_AUTHENTICATED', 'access': ledger,
                              'model_feature_label_members_materialized': 0},
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        with (run.HERE / 'FREEZE_AUTHENTICATION.json').open('xb') as f:
            f.write(witness)
        reg['provenance']['FREEZE_AUTHENTICATION.json'] = hashlib.sha256(witness).hexdigest()
        raw = json.dumps(reg, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        h = hashlib.sha256(raw).hexdigest()
        with (run.HERE / 'REGISTRY.json').open('xb') as f:
            f.write(raw)
        return h


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inherited-spec', required=True)
    p.add_argument('--inherited-spec-sha256', required=True)
    args = p.parse_args()
    print(freeze(args.inherited_spec, args.inherited_spec_sha256))
