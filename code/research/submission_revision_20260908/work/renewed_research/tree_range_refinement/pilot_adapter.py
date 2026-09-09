"""Explicit hash-gated adapter. Import performs no file or model access."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

KEYS = {'initial', 'nodes', 'nodes_offsets', 'raw_left_cat_bitsets',
        'raw_left_cat_bitsets_offsets', 'binned_left_cat_bitsets',
        'binned_left_cat_bitsets_offsets'}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def authenticate(registry_path, expected_sha):
    """Authenticate the finite registry and every source before model loading."""
    p = Path(registry_path).resolve()
    if sha(p) != expected_sha:
        raise ValueError('registry hash mismatch')
    r = json.loads(p.read_text())
    if r['scope'] != {'context': 'final', 'branch': 'proper', 'family': 'capped', 'dimensions': 62, 'stages': 400}:
        raise ValueError('unsupported scope')
    for name, item in r['sources'].items():
        q = (p.parent / item['path']).resolve()
        if sha(q) != item['sha256']:
            raise ValueError('source hash mismatch: ' + name)
    return r, p.parent


def source_module(r, root, key):
    item = r['sources'][key]
    path = (root / item['path']).resolve()
    if sha(path) != item['sha256']:
        raise ValueError('source mutation')
    spec = importlib.util.spec_from_file_location('authenticated_' + key, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model(r, root):
    """Real runner only. No call is made by registry creation or synthetic tests."""
    import numpy as np
    item = r['input']
    path = (root / item['path']).resolve()
    if sha(path) != item['sha256']:
        raise ValueError('model hash mismatch')
    # A conservative input guard is distinct from the algorithm state estimate.
    # It limits ZIP expansion before NumPy allocates any arrays.
    with zipfile.ZipFile(path) as z:
        info = z.infolist()
        if len(info) != len(KEYS) or {i.filename for i in info} != {k + '.npy' for k in KEYS}:
            raise ValueError('unexpected NPZ members')
        if any(i.is_dir() or i.flag_bits & 1 for i in info):
            raise ValueError('unsupported NPZ member')
        if sum(i.file_size for i in info) > 16 * 1024 * 1024:
            raise MemoryError('16 MiB uncompressed input guard')
    with np.load(path, allow_pickle=False) as a:
        if set(a.files) != KEYS:
            raise ValueError('NPZ schema')
        arrays = {k: a[k] for k in KEYS}
    evaluator = source_module(r, root, 'evaluator')
    model = evaluator.SequentialHist(arrays, required_stages=400)
    if sha(path) != item['sha256']:
        raise ValueError('model changed during load')
    return model


def inherited(r, root):
    """Existing certificate metadata, never represented as a new topology replay."""
    item = r['sources']['stage0_certificate']
    path = root / item['path']
    if sha(path) != item['sha256']:
        raise ValueError('Stage 0 certificate hash mismatch')
    certificate = json.loads(path.read_text())
    records = [v for v in certificate['records'] if v['context'] == 'final']
    if len(records) != 1 or records[0]['range'] != r['inherited_range']:
        raise ValueError('inherited range is not the authenticated final record')
    if certificate['accessed_tree_sha256']['arrays/tree_31_capped.npz'] != r['input']['sha256']:
        raise ValueError('inherited certificate model binding')
    return {'status': 'INHERITED_STAGE0_ONLY', 'scope': r['scope'],
            'range': r['inherited_range'], 'certificate_sha256': item['sha256'],
            'new_topology_replay': False, 'new_refinement_claim': False}
