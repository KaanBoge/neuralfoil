"""Pickle-free exact replay. Trust the externally supplied manifest SHA256."""
from pathlib import Path
from fractions import Fraction as F
import argparse, hashlib, json
import numpy as np

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rat(x):
    return F.from_float(float(x))

def rational_matches(value, expected):
    require(str(value.numerator) == expected['numerator'] and
            str(value.denominator) == expected['denominator'], 'rational mismatch')

def tree_bound(a, b):
    require(set(a.files) == set(b.files), 'array key mismatch')
    for key in a.files:
        require(a[key].dtype == b[key].dtype and np.array_equal(a[key], b[key]), 'representation mismatch: '+key)
    require(a['initial'].size == 1, 'initial shape')
    lo = hi = rat(a['initial'].ravel()[0])
    offsets = a['nodes_offsets']
    require(len(offsets) == 401 and offsets[0] == 0 and offsets[-1] == len(a['nodes']) and np.all(np.diff(offsets)>0), 'stage offsets')
    for key in ['raw_left_cat_bitsets', 'binned_left_cat_bitsets']:
        o = a[key+'_offsets']
        require(len(o)==401 and o[0]==0 and o[-1]==len(a[key]) and np.all(np.diff(o)>=0), 'bitset offsets')
    for start,end in zip(offsets[:-1],offsets[1:]):
        nodes = a['nodes'][start:end]
        leaves = nodes['value'][nodes['is_leaf'].astype(bool)]
        require(len(leaves)>0 and np.isfinite(leaves).all(), 'invalid leaves')
        lo += min(map(rat,leaves)); hi += max(map(rat,leaves))
    return lo,hi

def floor_bound(z):
    b,y,g = z['BASE_CD'],z['MEAS_CD'],z['group']
    require(b.ndim==y.ndim==g.ndim==1 and b.shape==y.shape==g.shape, 'calibration shapes')
    require(np.isfinite(b).all() and np.isfinite(y).all() and (b>0).all(), 'invalid calibration')
    maxima = {name:F(0) for name in np.unique(g)}
    for base,target,name in zip(b,y,g):
        base,target=rat(base),rat(target)
        maxima[name]=max(maxima[name],max(base/2-target,target-2*base,F(0))/base)
    m=len(maxima); k=(9*(m+1)+9)//10
    require(k<=m, 'infinite rank not present in frozen witness')
    return m,k,sorted(maxima.values())[k-1]

def verify(root, manifest_sha):
    root=Path(root).resolve(); manifest=root/'manifest.json'
    require(len(manifest_sha)==64 and sha(manifest)==manifest_sha, 'manifest authentication failed')
    meta=json.loads(manifest.read_text())
    for name,digest in meta['files'].items():
        p=(root/name).resolve()
        require(p.is_relative_to(root) and p.is_file() and not (root/name).is_symlink(), 'unsafe or missing file')
        require(sha(p)==digest, 'file authentication failed: '+name)
    expected=json.loads((root/'expected.json').read_text())
    require(len(meta['trees'])==32 and len(meta['floors'])==16, 'witness counts')
    for rec,ref in zip(meta['trees'],expected['trees']):
        require((rec['context'],rec['branch'])==(ref['context'],ref['branch']) and ref['stages']==400, 'tree context mismatch')
        with np.load(root/rec['capped'],allow_pickle=False) as a, np.load(root/rec['upper_free'],allow_pickle=False) as b:
            lo,hi=tree_bound(a,b)
        rational_matches(lo,ref['lower']); rational_matches(hi,ref['upper'])
        require(hi<1 and ref['exact_upper_below_one'], 'inactive bound mismatch')
    count=0
    for rec,ref in zip(meta['floors'],expected['floors']):
        require(rec['context']==ref['context'], 'floor context mismatch')
        with np.load(root/rec['file'],allow_pickle=False) as z:
            m,k,f=floor_bound(z)
        require((m,k)==(ref['groups'],ref['rank']), 'rank mismatch')
        rational_matches(f,ref['floor'])
        require(bool(f>=1)==ref['exact_floor_at_least_one'], 'floor flag mismatch')
        count+=int(f>=1)
    require(count==11, 'floor count mismatch')
    return dict(status='PASS',tree_pairs=32,tree_models=64,stages_per_model=400,
                exact_rational_comparisons=80,calibration_contexts=16,floor_at_least_one=11,
                authenticated_files=len(meta['files']),manifest_sha256=manifest_sha)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--manifest-sha256',required=True); args=p.parse_args()
    print(json.dumps(verify(args.root,args.manifest_sha256),indent=2))
