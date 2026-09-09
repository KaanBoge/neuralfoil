"""Root approval and bounded parent for the single reviewed SG-only diagnostic.

Preparation authenticates source/provenance only. --run executes the approved
three-call diagnostic once; no benchmark timings or actual retries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
HERE = ROOT / 'model_proposal/inference_benchmark_diagnosis/v2'
PIN = '43beec6c6cf19268b3876c4e7b3138aea570eee949b7ef1b99779530769a78aa'
def check(path, pin):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('symlink input')
    b = path.read_bytes()
    if hashlib.sha256(b).hexdigest() != pin:
        raise ValueError('changed source ' + str(path))
    return b
def main(run_pin=None):
    reg = json.loads(check(HERE / 'REGISTRY.json', PIN))
    for name,h in reg['sources'].items():
        assert Path(name).name == name
        check(HERE / name, h)
    check(ROOT / 'independent_environment/sg_diagnostic_v2_review/REPORT.md', 'afe504b1c93a08af9c8dfb7ab66b79b7fba51eb0b4813c80e8a1798cbadc287d')
    check(HERE / 'synthetic_attempt_1/DIAGNOSTICS.json', reg['preserved_failure_sha256'])
    check(HERE / 'synthetic_attempt_2/DIAGNOSTICS.json', reg['synthetic_evidence_sha256'])
    for name,h in reg['prefreeze_failure_sources'].items():
        check(HERE / 'prefreeze_failure_1' / name, h)
    tests = json.loads((HERE / 'ROOT_TEST_RESULT.json').read_bytes())
    assert tests['exit_code'] == 0 and 'Ran 12 tests' in tests['output'] and tests['output'].endswith('OK\n')
    out = HERE / 'actual_attempt_1'
    assert not out.exists()
    approval = dict(registry_sha256=PIN, phase='sg_reference_diagnostic', actual_execution_authorized=True,
        seconds=120, workers=1, rows=242, output_cap_bytes=8388608, members=reg['members'],
        output_path=str(out), runtime=reg['runtime'], entrypoint_sha256=reg['sources']['run.py'])
    raw = json.dumps(approval, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    h = hashlib.sha256(raw).hexdigest(); path = HERE / 'ROOT_ACTUAL_APPROVAL.json'
    if run_pin is None:
        with path.open('xb') as f:
            f.write(raw)
        print(json.dumps(dict(approval_sha256=h, phase='sg_reference_diagnostic', actual_calls_executed=0,
                             outer_child_timeout_seconds=120, benchmark_retry_authorized=False)))
        return
    assert h == run_pin
    check(path, run_pin)
    cmd = ['/opt/anaconda3/bin/python', '-B', str(HERE / 'run.py'), '--registry-sha256', PIN,
           '--approval', str(path), '--approval-sha256', run_pin]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    start = time.monotonic()
    # subprocess.run kills and waits for this sole direct child if its timeout expires.
    # This is an outer child wait deadline, not a CPU-time or real-time OS guarantee.
    result = subprocess.run(cmd, cwd=PROJECT, env=env, timeout=120, check=True)
    print(json.dumps(dict(status='ROOT_CHILD_EXIT_ZERO_REQUIRES_RESULT_REVIEW',
                          observed_parent_interval_seconds=time.monotonic()-start, returncode=result.returncode)))
if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run'); a = p.parse_args(); main(a.run)
