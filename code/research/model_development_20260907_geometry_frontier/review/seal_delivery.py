"""Read-only evidence authentication; writes only this round's DELIVERY_QA.json.

No producer imports, fitting, assessment regeneration, timing, or new data.
Existing numerical audits are authenticated, not represented as rerun here.
"""
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
verified = {}
comparisons = 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(path, expected):
    global comparisons
    path = Path(path)
    actual = sha(path)
    assert actual == expected, f'Hash changed: {path}'
    verified[str(path)] = actual
    comparisons += 1


def read(relative):
    path = ROOT / relative
    value = json.loads(path.read_text())
    verified[str(path)] = sha(path)
    return value


def hashes(mapping):
    for path, expected in mapping.items():
        check(path, expected)


def main():
    g = read('geometry/results/complete.json')
    gf = read('geometry/results/freeze.json')
    nf = read('neural/results/freeze.json')
    assert g['model_count'] == 64 and len(gf['model_sha256']) == 64
    assert gf['all_64_frozen_before_exposed'] is True
    assert nf['model_count'] == 48 and nf['external_scored_at_freeze'] is False
    assert gf['recovery_provenance']['preserved_original_models'] == 11
    assert gf['recovery_provenance']['successor_models'] == 53
    for mapping in (g['source_sha256'], g['evaluation_sha256'], gf['model_sha256'],
                    nf['source_input_sha256'], nf['artifact_sha256']):
        hashes(mapping)
    a = read('assessment/report.json')
    hashes(a['input_source_sha256'])
    hashes(a['output_sha256'])
    assert len(a['candidates']) == 6 and len(a['controls']) == 4
    assert a['panels'] == 31 and a['bootstrap_draws'] == 20000
    assert a['performance_advances'] == [] and a['robustness_advances'] == []
    audits = {name: read(f'review/{name}_audit.json')
              for name in ('geometry', 'neural', 'assessment', 'fast_inference')}
    assert all(x['status'] == 'PASS' for x in audits.values())
    assert audits['geometry']['router_models'] == 64
    assert audits['geometry']['prediction_values'] == 119424
    assert audits['geometry']['native_fallback_values'] == 100
    assert audits['neural']['models'] == 48 and audits['neural']['warning_fits'] == 14
    check(ROOT/'geometry/results/complete.json', audits['geometry']['geometry_complete_sha256'])
    check(ROOT/'assessment/report.json', audits['assessment']['assessment_report_sha256'])
    for name, script in [('geometry','audit_geometry.py'), ('assessment','audit_assessment.py'),
                         ('fast_inference','fast_inference_audit.py')]:
        check(ROOT/'review'/script, audits[name]['audit_code_sha256'])
    assert audits['assessment']['checks'] == dict(panels=310, harms=1240, groups=1860, bootstraps=40)
    with (ROOT/'assessment/decisions.csv').open() as stream:
        decisions = list(csv.DictReader(stream))
    assert {x['candidate'] for x in decisions} == set(a['candidates'])
    assert len(decisions) == 6
    for row in decisions:
        assert row['performance_advance'] == 'False' and row['robustness_advance'] == 'False'
    assert all(not d['performance_advance'] and not d['robustness_advance']
               for d in audits['assessment']['decisions'])
    cert = read('envelope/certificate.json')
    hashes(cert['source_sha256'])
    check(ROOT/'envelope/parsed_inputs.npz', cert['snapshot_sha256'])
    check(ROOT/'envelope/row_envelope.csv', cert['row_table_sha256'])
    for relative in ('envelope/verification.json', 'envelope/independent_verification.json'):
        v = read(relative)
        assert v['status'] == 'PASS' and v['baseline_comparisons'] == 62
        check(ROOT/'envelope/certificate.json', v['certificate_sha256'])
    q = cert['common_improvement_fraction_upper_bound']
    bound = Fraction(int(q['numerator']), int(q['denominator']))
    assert abs(float(bound)*100 - 15.9005587510) < 1e-9
    assert cert['all_panel_baseline_denominators_positive'] is True
    engineering = audits['fast_inference']
    check(ROOT/'engineering/fast_inference/results.json', engineering['producer_result_sha256'])
    assert engineering['labels'] == 3 and engineering['reference_rows_per_label'] == 8868
    assert engineering['timing_rerun'] is False
    for relative in ('REPORT.md', 'PROTOCOL.md', 'review/seal_delivery.py', 'review/audit_neural.py'):
        path = ROOT/relative
        verified[str(path)] = sha(path)
    # Detect changes during the seal, including source files visited more than once.
    for path, expected in list(verified.items()):
        assert sha(path) == expected, f'Changed during seal: {path}'
    result = dict(status='PASS', operation='Read-only authentication of completed evidence; no numerical audit rerun',
                  hash_comparisons=comparisons, unique_files=len(verified),
                  geometry_models=64, neural_models=48, neural_warning_fits=14,
                  assessment_checks=audits['assessment']['checks'], decisions=decisions,
                  oracle_upper_bound_percent=float(bound)*100,
                  oracle_is_label_knowing_not_model_accuracy=True,
                  engineering_is_separate_precomputed_feature_inference=True,
                  no_new_fits_or_outcomes=True, authenticated_sha256=verified)
    output = ROOT/'DELIVERY_QA.json'
    output.write_text(json.dumps(result, indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('decisions','authenticated_sha256')})


if __name__ == '__main__':
    main()
