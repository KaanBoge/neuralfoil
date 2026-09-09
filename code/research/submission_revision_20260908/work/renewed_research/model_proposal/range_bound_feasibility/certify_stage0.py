"""Read authenticated proper TREE arrays only; never read roles/outcomes/calibration."""
from pathlib import Path, PurePosixPath
from io import BytesIO
import argparse
import hashlib
import json
import re
import time
import numpy as np
import qualified_numerics as q

PIN = '210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_tree(root, name, hashes, accessed):
    if not re.fullmatch(r'arrays/tree_\d{2}_(capped|upper_free)\.npz', name):
        raise ValueError('only tree arrays may be opened')
    parts = PurePosixPath(name).parts
    path = root.joinpath(*parts)
    if any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts)+1)):
        raise ValueError('symlink tree path')
    data = path.read_bytes()
    if digest(data) != hashes[name]:
        raise ValueError('tree authentication failed')
    accessed[name] = digest(data)
    with np.load(BytesIO(data), allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def tree_stages(a):
    offsets, nodes = a['nodes_offsets'], a['nodes']
    if a['initial'].size != 1 or not np.isfinite(a['initial']).all():
        raise ValueError('initial prediction')
    if offsets.shape != (401,) or offsets[0] != 0 or offsets[-1] != len(nodes) or (np.diff(offsets)<=0).any():
        raise ValueError('exactly 400 stages required')
    for start, stop in zip(offsets[:-1], offsets[1:]):
        stage = nodes[start:stop]
        leaves = stage['value'][stage['is_leaf'].astype(bool)]
        if not len(leaves) or not np.isfinite(leaves).all():
            raise ValueError('invalid leaves')
        yield leaves


def certificate(root):
    started = time.monotonic()
    root = Path(root).resolve()
    raw = (root/'manifest.json').read_bytes()
    if digest(raw) != PIN:
        raise ValueError('pinned bounds manifest mismatch')
    manifest = json.loads(raw)
    accessed, records = {}, []
    hashes = manifest['files'] if 'files' in manifest else manifest['sha256']
    selected = [r for r in manifest['trees'] if r['branch'] == 'proper']
    if len(selected) != 16 or len({r['context'] for r in selected}) != 16:
        raise ValueError('expected 16 distinct proper contexts')
    for entry in selected:
        a = load_tree(root, entry['capped'], hashes, accessed)
        b = load_tree(root, entry['upper_free'], hashes, accessed)
        if set(a) != set(b) or any(a[k].dtype != b[k].dtype or not np.array_equal(a[k], b[k]) for k in a):
            raise ValueError('proper representation mismatch')
        bounds = q.sequential_range(a['initial'].ravel()[0], tree_stages(a))
        structural = q.structural_bound(bounds['lower'], bounds['upper'])
        if not 0 < structural < q.F(1, 2):
            raise ValueError('strict structural improvement not established')
        records.append({'context': entry['context'], 'range': bounds,
                        'B_structural': structural, 'B_generic': q.GENERIC_BOUND,
                        'B_structural_display': float(structural)})
    return {'status': 'STAGE0_LABEL_FREE_CERTIFICATE_ONLY',
            'numerical_assumptions': 'binary64 round-nearest ties-even, sequential 400-stage additions, separate nonfused core operations',
            'source_manifest_sha256': PIN, 'accessed_tree_sha256': accessed,
            'calibration_outcome_role_arrays_opened': 0,
            'real_data_strengths_or_losses_computed': False,
            'records': records, 'seconds': time.monotonic()-started,
            'implementation_sha256': {p.name: digest(p.read_bytes()) for p in
                                     [Path(__file__), Path(q.__file__)]}}


def encode(x):
    if isinstance(x, q.F):
        return {'numerator': str(x.numerator), 'denominator': str(x.denominator)}
    raise TypeError(type(x).__name__)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--tree-bundle', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    out = Path(args.output)
    if out.exists():
        raise FileExistsError('refuse overwrite')
    result = certificate(args.tree_bundle)
    with out.open('x') as f:
        json.dump(result, f, default=encode, indent=2)
        f.write('\n')
    print(json.dumps({'status': result['status'], 'contexts': len(result['records']),
                      'seconds': result['seconds']}))
