"""Exact binary-rational instantiation of two deterministic saved-artifact bounds."""
from pathlib import Path
from fractions import Fraction as F
import hashlib,json,pickle
import numpy as np
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rat(x):return F.from_float(float(x))
def encoded(x):return {'numerator':str(x.numerator),'denominator':str(x.denominator),'float_display':float(x)}
def main():
    a=PROJECT/'model_development_20260907_cap_ablation';s=PROJECT/'model_development_20260907_selective'
    ah=json.loads((a/'results/freeze.json').read_text());sh=json.loads((s/'results/freeze.json').read_text())
    witnesses={str(a/'results/freeze.json'):sha(a/'results/freeze.json'),str(s/'results/freeze.json'):sha(s/'results/freeze.json')}
    trees=[];floors=[]
    for context in ah['contexts']:
        for branch in ['full','proper']:
            models=[]
            for family in ['capped','upper_free']:
                p=a/f'results/core_{context}_{branch}_{family}.pkl';expected=ah['artifact_sha256'][str(p)];assert sha(p)==expected;witnesses[str(p)]=expected
                models.append(pickle.loads(p.read_bytes())['model'])
            x,y=models;np.testing.assert_array_equal(x._baseline_prediction,y._baseline_prediction)
            upper=rat(x._baseline_prediction.ravel()[0]);lower=upper
            for xs,ys in zip(x._predictors,y._predictors):
                assert len(xs)==len(ys)==1
                for key in ['nodes','raw_left_cat_bitsets','binned_left_cat_bitsets']:np.testing.assert_array_equal(getattr(xs[0],key),getattr(ys[0],key))
                leaves=xs[0].nodes['value'][xs[0].nodes['is_leaf'].astype(bool)]
                upper+=max(map(rat,leaves));lower+=min(map(rat,leaves))
            assert upper<1
            trees.append(dict(context=context,branch=branch,stages=len(x._predictors),upper=encoded(upper),lower=encoded(lower),exact_upper_below_one=True))
        p=s/f'results/calibration_{context}.npz';expected=sh['artifact_sha256'][str(p)];assert sha(p)==expected;witnesses[str(p)]=expected
        z=np.load(p);names=np.unique(z['group']);maxima={g:F(0) for g in names}
        for b,y,g in zip(z['BASE_CD'],z['MEAS_CD'],z['group']):
            b,y=rat(b),rat(y);assert b>0
            floor=max(b/2-y,y-2*b,F(0))/b;maxima[g]=max(maxima[g],floor)
        k=(9*(len(names)+1)+9)//10;assert k<=len(names)
        floor=sorted(maxima.values())[k-1]
        floors.append(dict(context=context,groups=len(names),rank=k,floor=encoded(floor),exact_floor_at_least_one=bool(floor>=1)))
    for p,h in witnesses.items():assert sha(p)==h
    result=dict(status='PASS',arithmetic='Exact rational arithmetic on IEEE-754 binary values parsed from authenticated arrays; no rounding in inequalities',trees=trees,floors=floors,tree_count=len(trees),inactive_upper_count=sum(t['exact_upper_below_one'] for t in trees),floor_context_count=len(floors),floor_at_least_one_count=sum(t['exact_floor_at_least_one'] for t in floors),source_sha256=witnesses,code_sha256=sha(Path(__file__)),limitations='Exact bounds concern real sums of saved binary coefficients and fixed observed calibration samples; runtime floating-point overflow/rounding and sampling validity are separate obligations.')
    (HERE/'EXACT_BOUNDS.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['trees','floors','source_sha256']})
if __name__=='__main__':main()
