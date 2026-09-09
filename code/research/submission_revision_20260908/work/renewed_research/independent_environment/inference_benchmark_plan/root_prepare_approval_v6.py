"""Root's one-attempt V6 approval, only after the owned-job quiet interval.

Source/metadata authentication only; this helper never runs inference or reads
scientific array members. Older approvals and failures are preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = next(p for p in HERE.parents if p.name == 'NeuralFoil_Research_Paper')
RESEARCH = HERE.parents[1]


def checked(path, pin):
    path = Path(path).absolute()
    if not path.is_relative_to(PROJECT) or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('source/metadata path')
    if path.stat().st_size > 2**20:
        raise ValueError('bounded metadata')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('source/metadata identity: '+str(path))
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--owned-jobs-quiet', action='store_true', required=True)
    args = parser.parse_args()
    if not args.owned_jobs_quiet:
        raise ValueError('explicit quiet confirmation required')
    regsha = '59aae736fae33f9ac2faede293152fec70e19496e4a2c7e6b627b998ebc17978'
    reg = json.loads(checked(HERE/'REGISTRY_v6.json', regsha))
    for key in ('sources', 'v5_sources'):
        for name, pin in reg[key].items():
            checked(HERE/name, pin)
    for name, pin in reg['preserved_v5_failure'].items():
        checked(HERE/'actual_v5_attempt_1'/name, pin)
    if (HERE/'actual_v5_attempt_1/COMPLETE.json').exists():
        raise ValueError('preserved V5 failure scope changed')
    review = checked(RESEARCH/'model_proposal/editorial/benchmark_v5_review/V6_IMPLEMENTATION_REVIEW.md',
                     '6890d898417496c40d329317b3186b70f24a73afc0c8388dbdff08771e6356ff').decode()
    if regsha not in review or '**PASS' not in review:
        raise ValueError('independent source review')
    checked(HERE/'V6_SOURCE_QA.json', 'e683819e60e197a7c76587e0644a9b5cbe518c686e4df65bc7df5850ae2feff1')
    old = json.loads(checked(HERE/'ROOT_ACTUAL_APPROVAL_V5.json',
                            '1904f3ff663c5339c11d52db27197e1ef07f17ae0e2259b9d0f3c6acb4abf5fd'))
    keys = ('runtime', 'max_seconds', 'max_request_seconds', 'max_rss_bytes',
            'max_output_bytes', 'routes', 'schedule', 'cold_repeats', 'warmups',
            'warm_repeats', 'workers', 'reference_contract')
    for key in keys:
        if old[key] != reg[key]:
            raise ValueError('unchanged scientific/resource contract '+key)
    out = HERE/'actual_v6_attempt_1'
    if out.exists():
        raise FileExistsError('preserve actual V6 attempts')
    old.update(authorized_phase='one_fixed_inference_benchmark_v6', registry_sha256=regsha,
               output=str(out), host_other_scientific_jobs_stopped=True)
    raw = (json.dumps(old, indent=2)+'\n').encode()
    path = HERE/'ROOT_ACTUAL_APPROVAL_V6.json'
    with path.open('xb') as stream:
        stream.write(raw)
    print(json.dumps({'approval': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'output': str(out), 'scientific_execution_performed': False}))


if __name__ == '__main__':
    main()
