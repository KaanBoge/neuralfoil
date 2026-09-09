"""Root source-only pin gate and one fixed label-free preflight approval.

No scientific archive parsing or phase execution. Outputs are exclusive.
"""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent
HERE = ROOT / 'model_proposal/paired_tree_plan/all_context_downstream_plan'
PIN = 'f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
ENTRY = 'da1345c050dc53f7337044e1c5fbbe900febe000d7e2eb651e64d47d804791ca'
def checked(p, pin):
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('symlink input')
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('changed source: ' + str(p))
    return raw
reg = json.loads(checked(HERE / 'REGISTRY.json', PIN))
assert reg['entrypoint_sha256'] == ENTRY
seen = {}
for section, base in [('sources', HERE), ('provenance', HERE), ('external_sources', ROOT)]:
    for rel, pin in reg[section].items():
        p = Path(rel)
        assert not p.is_absolute() and '..' not in p.parts
        checked(base / p, pin)
        seen[str((base / p).relative_to(ROOT))] = pin
assert len(reg['sources']) == 9 and len(reg['provenance']) == 11 and len(reg['external_sources']) == 37
assert not any((HERE / p).exists() for p in reg['phases'])
test = json.loads((HERE / 'ROOT_TEST_RESULT.json').read_bytes())
assert test['exit_code'] == 0 and 'Ran 27 tests' in test['output'] and test['output'].endswith('OK\n')
review = ROOT / 'uncertainty_review/range_bound_feasibility/DOWNSTREAM_SOURCE_FINAL_REVIEW.md'
assert PIN in review.read_text() and 'SOURCE-ONLY CLEARANCE' in review.read_text()
record = dict(status='ROOT_SOURCE_GATE_PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              registry_sha256=PIN, entrypoint_sha256=ENTRY, files=seen,
              independent_review_sha256=hashlib.sha256(review.read_bytes()).hexdigest(),
              root_test_sha256=hashlib.sha256((HERE / 'ROOT_TEST_RESULT.json').read_bytes()).hexdigest(),
              scientific_members_materialized=0, actual_phases_run=0,
              documentation_note='Handoff says eight inherited fields; code consistently requires seven.',
              reviewed_scope='Explicit serializers, inherited helper API, unchanged scientific ASTs, dual registry chain, single writer logical cap, finite phase output set, deadline and exclusive final commit.')
def save(p, obj):
    raw = json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with p.open('xb') as f:
        f.write(raw)
    return hashlib.sha256(raw).hexdigest()
gate = save(HERE / 'ROOT_SOURCE_GATE.json', record)
approval = dict(registry_sha256=PIN, phase='preflight', seconds=900, workers=1,
    actual_execution_authorized=True, output=str((HERE / 'preflight').relative_to(ROOT)),
    runtime='/opt/anaconda3/bin/python', contexts=reg['contexts'], output_roots=reg['output_roots'],
    logical_cap=reg['logical_cap'], failure_reserve=reg['failure_reserve'],
    inherited_certificate_registry_sha256=reg['inherited']['registry_sha256'],
    predecessor_sha256=reg['inherited']['replay_sha256'])
ap = save(HERE / 'ROOT_PREFLIGHT_APPROVAL.json', approval)
print(json.dumps(dict(source_gate_sha256=gate, approval_sha256=ap, phase='preflight', subsequent_phases_authorized=False)))
