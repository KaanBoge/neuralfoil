"""Untimed canonical-portable oracle and lossless discrepancy reporting only.

No model I/O or inference at import. The supplied functions are executed from
authenticated, unchanged original sources by loader_v5. Profile capture observes
the canonical function's own core, without reimplementing tree arithmetic.
"""
import sys
import hashlib
import numpy as np

CONTRACT='current_runtime_canonical_portable_bit_exact_with_separate_archive_inventory_v1'

def same(a,b,name='array'):
    a=np.asarray(a);b=np.asarray(b)
    if a.dtype.hasobject or b.dtype.hasobject or a.shape!=b.shape or a.dtype!=b.dtype or a.tobytes(order='C')!=b.tobytes(order='C'):
        raise ValueError('bit-exact shape/dtype/value mismatch '+name)

def exact(actual,expected):
    if actual.keys()!=expected.keys():raise ValueError('output keys')
    for k in actual:same(actual[k],expected[k],k)

def inventory(current,archived):
    a=np.asarray(current);b=np.asarray(archived)
    if a.dtype!=np.dtype('float64') or b.dtype!=a.dtype or a.ndim!=1 or a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all() or (a<=0).any() or (b<=0).any():
        raise ValueError('archive comparison shape/dtype/positive finite')
    av=a.view(np.uint64);bv=b.view(np.uint64)
    def ordered(x):
        n=int(x);return (~n)&((1<<64)-1) if n>>63 else n|(1<<63)
    rows=[]
    for i in np.flatnonzero(av!=bv):
        rows.append({'row_index':int(i),'current_hex':float(a[i]).hex(),'archived_hex':float(b[i]).hex(),'current_bits':f'{int(av[i]):016x}','archived_bits':f'{int(bv[i]):016x}','ulp_distance':abs(ordered(av[i])-ordered(bv[i])),'absolute_difference':float(abs(a[i]-b[i]))})
    return {'scope':'diagnostic archive comparison, not an archive identity PASS or a causal diagnosis','rows':len(a),'different_rows':len(rows),'bit_exact':not rows,'current_sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest(),'archived_sha256':hashlib.sha256(b.tobytes(order='C')).hexdigest(),'max_ulp':max((x['ulp_distance'] for x in rows),default=0),'max_absolute_difference':max((x['absolute_difference'] for x in rows),default=0.),'differences':rows}

class CanonicalOracle:
    def __init__(self,portable_predict,native_predict,artifact):
        self.portable_predict=portable_predict;self.native_predict=native_predict;self.artifact=artifact

    def evaluate(self,features,gate,saved_core):
        """Untimed, whole-cohort canonical call and independent saved-core check."""
        x,b,a=(features[k] for k in ['X62','BASE_CD','all_model_CD'])
        args=[x,b,a,gate,saved_core];before=[np.asarray(v).copy() for v in args]
        captured={};previous=sys.getprofile()
        def observe(frame,event,arg):
            if frame.f_code is self.portable_predict.__code__ and event=='return':
                c=frame.f_locals.get('c')
                if not isinstance(c,np.ndarray):raise ValueError('canonical core capture missing')
                captured['core']=c.copy()
        try:
            sys.setprofile(observe)
            cd,strength=self.portable_predict(self.artifact,x,b,a,gate,label='unpenalized_transfer')
        finally:sys.setprofile(previous)
        if 'core' not in captured:raise ValueError('canonical core capture missing')
        same(captured['core'],saved_core,'canonical saved native core')
        native_cd,native_strength=self.native_predict(self.artifact['policies']['unpenalized_transfer'],b,saved_core,a,gate=gate)
        exact({'CD':cd,'strength':strength},{'CD':native_cd,'strength':native_strength})
        for v,old in zip(args,before):same(v,old,'oracle input mutation')
        same(cd[~gate],b[~gate],'canonical supplied-gate fallback')
        return {'CD':cd.copy(),'strength':strength.copy()}
