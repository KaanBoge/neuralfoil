"""Saved synthetic receipts only; no scientific imports or model execution."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent
ROOT = PLAN.parents[1]
GATE_SHA = '72f715cb2fb2be83fcd6f98d7c02961af55bd5e1a7501e8537b9c12867571852'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(65536), b''):
            h.update(part)
    return h.hexdigest()


def main():
    attempt = PLAN/'synthetic_gate_attempt_1'
    pins = {}
    def pin(path, expected=None):
        assert not any(p.is_symlink() for p in (path, *path.parents))
        h = digest(path)
        if expected is not None:
            assert h == expected, str(path)
        pins[str(path.relative_to(ROOT))] = h
        return h
    pin(attempt/'GATE.json', GATE_SHA)
    gate = json.loads((attempt/'GATE.json').read_bytes())
    pin(attempt/'COMPLETE.json')
    complete = json.loads((attempt/'COMPLETE.json').read_bytes())
    assert complete['status'] == 'COMPLETE' and complete['summary'] == gate
    pin(PLAN/'GATE_REGISTRY.json', complete['registry_sha256'])
    reg = json.loads((PLAN/'GATE_REGISTRY.json').read_bytes())
    pin(PLAN/'ROOT_GATE_APPROVAL.json', complete['approval_sha256'])
    approval = json.loads((PLAN/'ROOT_GATE_APPROVAL.json').read_bytes())
    pin(PLAN/'ROOT_GATE_SOURCE_REVIEW.json', approval['source_review_sha256'])
    assert complete['source_pins'] == reg['sources']
    assert complete['helper_pins'] == reg['helpers']
    for name, h in reg['sources'].items():
        pin(PLAN/name, h)
    for entry in reg['helpers'].values():
        pin(ROOT/entry['path'], entry['sha256'])
    for name, h in complete['outputs'].items():
        pin(attempt/name, h)
    assert set(p.name for p in attempt.iterdir()) == set(complete['outputs'])|{'COMPLETE.json'}
    access = json.loads((attempt/'ACCESS.json').read_bytes())
    events = [x for x in access if 'path' in x and 'sha256' in x]
    for x in events:
        pin(Path(x['path']), x['sha256'])
    source_paths = {str(PLAN/n) for n in reg['sources']}
    source_paths |= {str(ROOT/e['path']) for e in reg['helpers'].values()}
    source_paths |= {str(PLAN/n) for n in ('GATE_REGISTRY.json','ROOT_GATE_APPROVAL.json','ROOT_GATE_SOURCE_REVIEW.json')}
    assert all(sum(x['path'] == p for x in events) == 2 for p in source_paths)
    assert not any('NPZ' in x['operation'] or 'materializ' in x['operation'] for x in access)
    result = gate['independent_result']
    assert result['counts'] == dict(blocks=50, feasible_pairs=315000, pair_classifications=315000, path_edges=47600, paths=6000, stages=400)
    assert result['branch_witness_checks'] == 4998000 and result['records'] == 452
    assert result['final'] == result['original_four']
    with (attempt/'certificate.jsonl').open('rb') as f:
        lines = sum(1 for _ in f)
    assert lines == 452
    assert (attempt/'certificate.jsonl').stat().st_size == result['stream_bytes'] == 4540831
    assert result['stream_sha256'] == complete['outputs']['certificate.jsonl']
    assert gate['actual_model_materializations'] == 0
    for phase, cap in (('preparation',256*2**20),('producer',128*2**20),('checker',256*2**20)):
        assert 0 <= gate[phase]['owned_estimate'] <= cap
        assert 0 <= gate[phase]['seconds'] <= 120
    size = sum(p.stat().st_size for p in attempt.iterdir())
    assert size <= 64*2**20 and complete['elapsed_seconds'] <= 900
    qa = dict(status='PASS_SAVED_SYNTHETIC_RECEIPT_AUDIT', reviewed_utc=datetime.now(timezone.utc).isoformat(),
              receipt_sha256=pins[str((attempt/'COMPLETE.json').relative_to(ROOT))], source_sha256=digest(Path(__file__)),
              pins=pins, unique_pins=len(pins), ledger_records=len(access), source_start_end_pairs=len(source_paths),
              actual_directory_bytes=size, reported_midphase_logical_bytes=gate['checker']['logical_output_bytes'],
              output_sizes={p.name:p.stat().st_size for p in attempt.iterdir()}, counts=result['counts'],
              certificate_lines=lines, phase_seconds=complete['elapsed_seconds'], phases={k:gate[k] for k in ('preparation','producer','checker')},
              synthetic_final_equals_original_four=True, actual_model_materializations=0,
              limitations=['Saved-output authentication, not rerun of the independent checker.',
                           'Owned-memory formulas are engineering estimates, not RSS measurements.',
                           'Manufactured fixture feasibility gives no actual-model tightening or aerodynamic gain.'])
    with (HERE/'QA.json').open('x') as f:
        json.dump(qa, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(qa, sort_keys=True))


if __name__ == '__main__':
    main()
