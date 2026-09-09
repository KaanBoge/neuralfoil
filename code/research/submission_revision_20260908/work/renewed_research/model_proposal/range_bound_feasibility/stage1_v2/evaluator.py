"""Numeric-only float64 HGB evaluator, local children and sequential leaf sums."""
import numpy as np


class SequentialHist:
    def __init__(self, arrays, required_stages=400):
        a = {k: np.array(v, copy=True) for k,v in arrays.items()}
        offsets, nodes = a['nodes_offsets'], a['nodes']
        if a['initial'].dtype != np.dtype('float64') or a['initial'].size != 1 or not np.isfinite(a['initial']).all():
            raise ValueError('finite initial scalar required')
        if offsets.dtype.kind not in 'iu' or offsets.shape != (required_stages+1,):
            raise ValueError('stage count or offsets dtype')
        if offsets[0] != 0 or offsets[-1] != len(nodes) or np.any(np.diff(offsets)<=0):
            raise ValueError('invalid offsets')
        if not {'value','is_leaf','feature_idx','num_threshold','left','right',
                'missing_go_to_left','is_categorical'}.issubset(nodes.dtype.names or ()):
            raise ValueError('incomplete node schema')
        if any(nodes.dtype.fields[k][0].kind not in 'iu' for k in
               ['is_leaf','feature_idx','left','right','missing_go_to_left','is_categorical']):
            raise ValueError('integer node index/flag fields required')
        if any(nodes.dtype.fields[k][0] != np.dtype('float64') for k in ['value','num_threshold']):
            raise ValueError('binary64 node values/thresholds required')
        for key in ['raw_left_cat_bitsets','binned_left_cat_bitsets']:
            if a[key+'_offsets'].shape != (required_stages+1,) or a[key].size or np.any(a[key+'_offsets'] != 0):
                raise ValueError('categorical bitsets unsupported')
        self.stages = []
        for start,stop in zip(offsets[:-1],offsets[1:]):
            t=nodes[start:stop].copy()
            for flag in ['is_leaf','missing_go_to_left','is_categorical']:
                if not np.isin(t[flag],[0,1]).all(): raise ValueError('nonbinary flag')
            if t['is_categorical'].any(): raise ValueError('categorical node unsupported')
            if not np.isfinite(t['value']).all(): raise ValueError('nonfinite node values')
            seen=set(); parents=np.zeros(len(t),int); stack=[0]
            while stack:
                j=stack.pop()
                if j in seen: raise ValueError('cycle or repeated parent')
                seen.add(j)
                if t['is_leaf'][j]: continue
                f=int(t['feature_idx'][j])
                if not 0 <= f < 62 or not np.isfinite(t['num_threshold'][j]):
                    raise ValueError('invalid numeric split')
                for key in ['left','right']:
                    child=int(t[key][j])
                    if not 0 <= child < len(t): raise ValueError('nonlocal child')
                    parents[child]+=1
                    if parents[child]>1: raise ValueError('multiple parent')
                    stack.append(child)
            if len(seen) != len(t) or parents[0] != 0:
                raise ValueError('unreachable node or root parent')
            t.setflags(write=False)
            self.stages.append(t)
        self.initial=float(a['initial'].ravel()[0])

    def predict_raw(self, features):
        # Probe both adjacent tie parities; reject the common directed modes.
        u=2.**-53
        if not np.array_equal(np.add(np.array([1.,1.+2*u]),u),np.array([1.,1.+4*u])):
            raise ValueError('round-nearest ties-even probe failed')
        x=np.asarray(features)
        if x.dtype != np.dtype('float64') or x.ndim != 2 or x.shape[1] != 62 or not np.isfinite(x).all():
            raise ValueError('finite float64 n-by-62 features required')
        out=np.full(len(x),self.initial,dtype=np.float64)
        rows=np.arange(len(x))
        for stage in self.stages:
            node=np.zeros(len(x),dtype=np.intp)
            active=~stage['is_leaf'][node].astype(bool)
            steps=0
            while active.any():
                rr=rows[active]; nn=node[active]
                left=x[rr,stage['feature_idx'][nn].astype(np.intp)] <= stage['num_threshold'][nn]
                node[active]=np.where(left,stage['left'][nn],stage['right'][nn])
                active=~stage['is_leaf'][node].astype(bool)
                steps+=1
                if steps>len(stage): raise ValueError('termination invariant')
            # One addition per tree, never a cross-stage reduction or LR rescaling.
            out += stage['value'][node]
        if not np.isfinite(out).all(): raise ValueError('nonfinite raw result')
        return out
