"""Read-only complete producer-chain audit; no model parsing or proof replay."""
import datetime
import hashlib
import json
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / 'model_proposal/paired_tree_plan/all_context_plan'
REG = '0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a'
PIN = '0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd'
APPROVAL = '16e49456ef74c209bbbe95194fae3f3c7c706aa28868cdc7cb0cce9587bfcb57'
ADAPTER = 'f76393b6d6cac459a04051551936624646dbf24adae00262eb67720cc0a90e82'

def raw(path, pin):
    value = path.read_bytes()
    assert hashlib.sha256(value).hexdigest() == pin, str(path)
    return value

def main():
    registry = json.loads(raw(PLAN / 'REGISTRY_v3.json', REG))
    for name, pin in registry['sources'].items():
        raw(PLAN / name, pin)
    for name, pin in registry['external_sources'].items():
        raw(ROOT / name, pin)
    code = raw(PLAN / 'adapter.py', ADAPTER)
    module = types.ModuleType('root_receipt_adapter')
    module.__file__ = str(PLAN / 'adapter.py')
    exec(compile(code, module.__file__, 'exec'), module.__dict__)
    ledger = []
    result = module.certificate_chain('certificates_produce', PIN, REG, ledger)
    approval = json.loads(raw(PLAN / 'ROOT_PRODUCER_APPROVAL_V3.json', APPROVAL))
    assert result['approval_sha256'] == APPROVAL
    assert approval['contexts'] == module.CONTEXTS
    assert result['summary']['fresh_contexts'] == 15
    assert result['summary']['inherited_contexts'] == 1
    assert result['summary']['features_targets_loaded'] == result['summary']['fits'] == 0
    assert 0 < result['seconds'] < approval['seconds'] == 900
    states = json.loads((PLAN / 'certificates_produce/CONTEXT_STATUS.json').read_bytes())
    assert states == {c: 'INHERITED_AUTHENTICATED' if c == 'final' else 'COMPLETE' for c in module.CONTEXTS}
    children = result['summary']['contexts']
    for context in module.CONTEXTS[:-1]:
        child = json.loads((PLAN / 'certificates_produce' / context / 'COMPLETE.json').read_bytes())
        assert child['approval_sha256'] == APPROVAL
        assert child['summary']['fits'] == child['summary']['features_targets_loaded'] == 0
        assert child['summary']['estimated_owned_peak_bytes'] <= 128 * 2**20
    logical_bytes = module.extension_usage()
    assert logical_bytes == 548863520 < module.LOGICAL_CAP
    assert not (PLAN / 'certificates_replay').exists()
    raw(PLAN / 'certificates_produce/COMPLETE.json', PIN)
    out = {
        'status': 'PASS_COMPLETE_PRODUCER_RECEIPT_CHAIN_NOT_PROOF_REPLAY',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'registry_sha256': REG, 'producer_complete_sha256': PIN,
        'approval_sha256': APPROVAL, 'contexts': module.CONTEXTS,
        'aggregate_outputs': len(result['outputs']),
        'authenticated_access_records': len(ledger),
        'producer_seconds': result['seconds'], 'logical_bytes': logical_bytes,
        'estimated_owned_peak_bytes': max(children[c]['estimated_owned_peak_bytes'] for c in module.CONTEXTS[:-1]),
        'actual_models_materialized_by_this_audit': 0,
        'actual_proofs_reexecuted_by_this_audit': 0,
        'source_and_output_pins_rechecked': True,
    }
    target = ROOT / 'ROOT_PAIRED_PRODUCER_RECEIPT_1832.json'
    with target.open('x') as stream:
        json.dump(out, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(out, sort_keys=True))

if __name__ == '__main__':
    main()
