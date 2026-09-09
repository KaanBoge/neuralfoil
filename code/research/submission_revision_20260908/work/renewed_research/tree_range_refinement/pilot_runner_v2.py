"""Single-context pilot. Real execution requires explicit registry SHA approval.

Default CLI only shows help. No model access occurs on import or preparation.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

import pilot_adapter as adapter


def exclusive_json(path, value, interrupt=None, serialization_interrupt=None):
    """Never expose partial JSON as a checkpoint; preserve interrupted .partial."""
    path = Path(path)
    partial = path.with_name(path.name + '.partial')
    if path.exists():
        raise FileExistsError(path)
    with partial.open('xb') as f:
        for chunk in json.JSONEncoder(indent=2, allow_nan=False).iterencode(value):
            f.write(chunk.encode())
            if serialization_interrupt:
                serialization_interrupt(chunk)
        f.write(b'\n')
        f.flush()
        os.fsync(f.fileno())
        if interrupt:
            interrupt()
    # Hard link publication is atomic and refuses collisions (unlike replace).
    os.link(partial, path)
    partial.unlink()
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def worker(args, r, root):
    from pilot_engine_v2 import Limits, refine
    model = adapter.load_model(r, root)
    q = adapter.source_module(r, root, 'qualified_numerics')
    limits = Limits(model.stages, seconds=120)
    def publish(state):
        exclusive_json(Path(args.output)/('candidate_%03d.json' % state['splits']), state)
    try:
        final_state, stop_reason = refine(model.stages, model.initial, q.sequential_range, limits, publish)
        status = 'SEARCH_RETURNED'
    except BaseException as exc:
        exclusive_json(Path(args.output)/'worker_failure.json', {'traceback': traceback.format_exc()})
        status = 'SEARCH_INTERRUPTED_OR_FAILED'
        stop_reason = type(exc).__name__ + ': ' + str(exc)
    exclusive_json(Path(args.output)/'worker_status.json', {
        'status': status, 'stop_reason': stop_reason,
        'completed_splits': limits.completed_splits, 'root_initialized': limits.initialized,
        'node_visits': limits.visits,
        'peak_algorithm_owned_estimate_bytes': limits.peak_estimate,
        'process_ru_maxrss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'rss_is_not_limited_by_algorithm_estimate': True})


def check(args, r, root):
    from pilot_checker import replay
    model = adapter.load_model(r, root)
    q = adapter.source_module(r, root, 'qualified_numerics')
    path = Path(args.candidate)
    before = adapter.sha(path)
    result = replay(json.loads(path.read_text()), model.stages, model.initial,
                    q.sequential_range, deadline=time.monotonic()+60)
    if adapter.sha(path) != before:
        raise ValueError('checkpoint mutation')
    result.update(candidate_sha256=before, model_sha256=r['input']['sha256'],
                  registry_sha256=args.approved_registry_sha256)
    result['B_structural'] = str(q.structural_bound(result['lower'], result['upper']))
    exclusive_json(Path(args.output)/'verified.json', result)


def orchestrate(args, r, root):
    out = Path(args.output).resolve()
    out.mkdir(parents=False, exist_ok=False)
    start = time.monotonic()
    exclusive_json(out/'checkpoint_000_inherited.json', adapter.inherited(r, root))
    exclusive_json(out/'start.json', {'registry_sha256': args.approved_registry_sha256,
                   'context': r['scope'], 'pid': os.getpid(), 'search_seconds_max': 120,
                   'search_and_verification_seconds_max': 180})
    command = [sys.executable, str(Path(__file__).resolve()), '--registry', str(Path(args.registry).resolve()),
               '--approved-registry-sha256', args.approved_registry_sha256, '--output', str(out)]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    def run(mode, extra, seconds):
        with (out/(mode+'.stdout.txt')).open('xb') as stdout, (out/(mode+'.stderr.txt')).open('xb') as stderr:
            try:
                p = subprocess.run(command+['--mode', mode]+extra, env=env, stdout=stdout,
                                   stderr=stderr, timeout=max(.001, seconds), check=False)
                return {'returncode': p.returncode, 'timeout': False}
            except subprocess.TimeoutExpired:
                return {'returncode': None, 'timeout': True}
    search = run('worker', [], min(120, 180-(time.monotonic()-start)))
    # Explicit finite checkpoint set, never glob failure or partial files.
    candidates = [out/('candidate_%03d.json' % n) for n in (128,64,16,4,1,0)]
    latest = next((p for p in candidates if p.is_file()), None)
    remaining = 180-(time.monotonic()-start)
    verification = None
    if latest is not None and remaining > 0:
        verification = run('check', ['--candidate', str(latest)], min(60, remaining))
    verified = out/'verified.json'
    result = adapter.inherited(r, root)
    if verified.exists() and verification and verification['returncode'] == 0:
        value = json.loads(verified.read_text())
        if value['candidate_sha256'] != adapter.sha(latest) or value['model_sha256'] != r['input']['sha256'] or value['registry_sha256'] != args.approved_registry_sha256 or value['status'] != 'PASS_FULL_DOMAIN_REPLAY':
            raise ValueError('verification receipt binding')
        result = value
    result.update(search=search, verification=verification, seconds=time.monotonic()-start,
                  scope_note='Label-free output enclosure only; not predictive improvement; no calibration or outcomes.')
    # Reauthenticate sources at handoff, without loading model arrays again.
    adapter.authenticate(args.registry, args.approved_registry_sha256)
    exclusive_json(out/'FINAL.json', result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry', required=True)
    p.add_argument('--approved-registry-sha256', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=['run','worker','check'], default='run')
    p.add_argument('--candidate')
    args = p.parse_args()
    r, root = adapter.authenticate(args.registry, args.approved_registry_sha256)
    {'run': orchestrate, 'worker': worker, 'check': check}[args.mode](args, r, root)


if __name__ == '__main__':
    main()
