"""Mechanical fixed next-phase approval after an explicitly pinned root-read review.

This does not execute any scientific phase and never overwrites an approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
HERE = ROOT / 'model_proposal/paired_tree_plan/all_context_downstream_plan'
CHAIN = {'calibrate':'preflight', 'score':'calibrate', 'assess':'score'}
REG = 'f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
def checked(p, h):
    p = p.absolute()
    assert p.is_relative_to(ROOT) and not any(x.is_symlink() for x in (p,*p.parents))
    b = p.read_bytes()
    if hashlib.sha256(b).hexdigest() != h:
        raise ValueError('changed pinned input: ' + str(p))
    return b
def main():
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=list(CHAIN))
    for key in ('predecessor-sha256','review','review-sha256'):
        p.add_argument('--'+key, required=True)
    a = p.parse_args()
    previous = CHAIN[a.phase]
    r = json.loads(checked(HERE / previous / 'COMPLETE.json', a.predecessor_sha256))
    assert r['status'] == 'COMPLETE' and r['phase'] == previous and r['registry_sha256'] == REG
    assert not (HERE / previous / 'FAILURE.json').exists()
    for name, h in r['outputs'].items():
        assert Path(name).name == name
        checked(HERE / previous / name, h)
    review = checked(Path(a.review), a.review_sha256).decode('utf-8')
    assert a.predecessor_sha256 in review and 'PASS' in review
    checked(HERE / 'REGISTRY.json', REG)
    original = json.loads(checked(HERE / 'ROOT_PREFLIGHT_APPROVAL.json', 'b6073acc3f74114cef2fb9e9626a1805a1c4cd6e39b850b7642a46566dd35932'))
    original.update(phase=a.phase, output=str((HERE / a.phase).relative_to(ROOT)), predecessor_sha256=a.predecessor_sha256)
    assert not (HERE / a.phase).exists()
    raw = json.dumps(original, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    target = HERE / ('ROOT_'+a.phase.upper()+'_APPROVAL.json')
    with target.open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(phase=a.phase, approval_path=str(target), approval_sha256=hashlib.sha256(raw).hexdigest(),
                         predecessor_sha256=a.predecessor_sha256, review_sha256=a.review_sha256,
                         subsequent_phases_authorized=False)))
if __name__ == '__main__': main()
