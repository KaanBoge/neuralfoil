"""Exact binary-rational all-knot check on the smallest actual historical bundle."""
from pathlib import Path
from fractions import Fraction as F
import hashlib,json
import numpy as np
import pandas as pd
from audit_empirical import DirectCurve

HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[3]
SOURCE=PROJECT/'model_development_20260908_adaptive_scale/assessment/all_row_predictions.csv'

def main():
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest!='c8f546532a90673ca0b9f2f4dce4e07ac215ed0160919de3e15c8396fe974c6a':raise ValueError('Source changed')
    frame=pd.read_csv(SOURCE,low_memory=False)
    f=frame[frame.split.str.startswith('group_20260906_')]
    group=f.groupby('group').size().sort_values().index[0];f=f[f.group.eq(group)];n=len(f)
    records=[]
    for base in ['mean8_CD','xlarge_CD']:
        for weighting in ['row','equal_bundle']:
            for r in [0.,.09]:
                b=f[base].to_numpy();c=f.unpenalized_transfer.to_numpy();y=f.measured_CD.to_numpy()
                w=np.full(n,1/8371 if weighting=='row' else 1/(93*n))
                rows=[tuple(F(float(x)) for x in z) for z in zip(b,c,y,w)]
                fr=F(r);ep=F(1);knots={-ep,ep}
                for bi,ci,yi,wi in rows:
                    knots.update(x for x in [-yi,bi-yi,ci-yi] if -ep<=x<=ep)
                values=[]
                for d in knots:
                    total=F(0)
                    for bi,ci,yi,wi in rows:
                        t=max(F(0),yi+d)
                        total+=wi*((1-fr)*abs(bi-t)-abs(ci-t))
                    values.append(total)
                exact=min(values),max(values)
                numeric=DirectCurve(b,c,y,w,r).bounds(1)
                error=max(abs(float(a)-z) for a,z in zip(exact,numeric))
                assert error<1e-13
                records.append(dict(baseline=base,weighting=weighting,target=r,knots=len(knots),maximum_difference=error,
                    exact_lower={'numerator':str(exact[0].numerator),'denominator':str(exact[0].denominator)},
                    exact_upper={'numerator':str(exact[1].numerator),'denominator':str(exact[1].denominator)}))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest
    result=dict(status='PASS',group=group,rows=n,comparisons=len(records),source_sha256=digest,results=records)
    (HERE/'SMALL_EXACT_QA.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))

if __name__=='__main__':main()
