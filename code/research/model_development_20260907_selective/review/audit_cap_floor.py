"""Independent CSV/reference alignment and finite calibration cap-floor replay."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    c=json.loads((ROOT/'results/complete.json').read_text());rows=[];csv_values=0;fallback=0
    for path,h in c['output_sha256'].items():assert sha(path)==h
    for record in c['splits']:
        name=record['split'];z=np.load(ROOT/f'results/calibration_{name}.npz')
        y,b,g=[z[k] for k in ['MEAS_CD','BASE_CD','group']]
        e=np.maximum.reduce([.5*b-y,y-2*b,np.zeros(len(b))])/b
        group=np.unique(g);floor=np.array([e[g==v].max() for v in group]);rank=(9*(len(group)+1)+9)//10
        qfloor=np.inf if rank>len(group) else sorted(floor)[rank-1]
        q=record['q'];assert q is not None and qfloor<=q+1e-13
        rows.append(dict(context=name,q=q,q_floor=float(qfloor),chosen_core_mean8_identity_every_valid_input=bool(q>=1),all_bounded_cores_mean8_identity_for_fixed_calibration=bool(qfloor>=1)))
    for path,h in c['output_sha256'].items():
        p=Path(path)
        if p.suffix!='.csv':continue
        ext=p.parent.name=='exposed_results';name=p.stem.replace('_predictions','') if ext else p.stem[len('predictions_'):]
        ref=p.parent/(name+'_inference.npz' if ext else 'inference_'+name+'.npz');z=np.load(ref);f=pd.read_csv(p)
        for key in ['project_mean8','project_xlarge','proper_core','proper_half','interval_lower','interval_upper']:
            np.testing.assert_allclose(f[key],z[key],rtol=0,atol=1e-13);csv_values+=len(f)
        for label,key in [('project_mean8','BASE_CD'),('project_xlarge','XLARGE_CD')]:
            # Stronger than fallback: both projections equal their native baseline on every reference.
            np.testing.assert_array_equal(z[label],z[key]);assert not z[label+'__intervened'].any()
            fallback+=int((~z['gate']).sum())
    summary=pd.read_csv(ROOT/'work/calibration_context_summary.csv').set_index('context')
    for r in rows:np.testing.assert_allclose(summary.loc[r['context'],'q'],r['q'],rtol=0,atol=1e-13)
    result=dict(status='PASS',contexts=rows,csv_numeric_values=csv_values,external_exact_fallback_values=fallback,
                chosen_core_q_ge_one_contexts=sum(r['chosen_core_mean8_identity_every_valid_input'] for r in rows),
                cap_floor_ge_one_contexts=sum(r['all_bounded_cores_mean8_identity_for_fixed_calibration'] for r in rows),
                scope='Calibration outcome bound for the fixed score/split and bounded core class, not physical noise or population optimum',
                complete_sha256=sha(ROOT/'results/complete.json'),code_sha256=sha(Path(__file__)))
    (ROOT/'review/cap_floor_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result)
if __name__=='__main__':main()
