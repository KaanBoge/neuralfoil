"""Independent numerical reconciliation of already-exposed Cycle 3 diagnostics."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
EX=ROOT/'exposed_results'
results=json.loads((EX/'results.json').read_text())
freeze=json.loads((ROOT/'results/freeze.json').read_text())
manifest=json.loads((ROOT/'results/run_manifest.json').read_text())
labels=manifest['candidate_labels']+list(freeze['selected'])
assert results['manifest']['selected']==freeze['selected']
frames={};checks=[];headline=[]
for name in ['SG_exposed','W_new_challenge']:
    f=pd.read_csv(EX/(name+'_predictions.csv'),float_precision='round_trip')
    original=pd.read_csv(ROOT.parent/'model_development_20260906_v2/external_results'/(name+'_predictions.csv'))
    assert len(f)==len(original)
    assert not f[['configuration','block','source_line']].duplicated().any()
    for col in original:
        if pd.api.types.is_numeric_dtype(original[col]):assert np.allclose(f[col],original[col],equal_nan=True,atol=1e-14,rtol=0),col
        else:assert np.array_equal(f[col].fillna(''),original[col].fillna('')),col
    with np.load(ROOT/'exposed_inputs/forward_verified'/(name+'.npz'),allow_pickle=False) as z:
        assert all(len(z[k])==len(f) and np.isfinite(z[k]).all() for k in z.files)
        assert np.array_equal(z['Re'],f.Re) and np.array_equal(z['alpha'],f.alpha)
        assert np.allclose(z['BASE_CD'],f.mean8_CD,atol=1e-14,rtol=0)
        assert np.allclose(z['XLARGE_CD'],f.xlarge_CD,atol=1e-14,rtol=0)
        assert np.array_equal(z['X9'],z['X16'][:,[0,1,2,4,8,9,10,12,13]])
        assert np.array_equal(z['X16'],z['X24'][:,:16])
        assert np.allclose(z['X16'][:,0],f.alpha,atol=1e-14,rtol=0)
        assert np.allclose(z['X16'][:,1],np.log10(f.Re),atol=1e-14,rtol=0)
        assert np.allclose(z['X16'][:,2],f.thickness_ratio,atol=1e-14,rtol=0)
        assert np.allclose(z['all_model_CD'].mean(axis=1),f.mean8_CD,atol=1e-14,rtol=0)
    domain=(f.Re>0)&(f.Re<=600000)&f.alpha.abs().le(12)&f.thickness_ratio.between(.05,.2)&f.mean8_CD.gt(0)
    assert np.array_equal(domain,f.inference_gate) and np.array_equal(domain&f.measured_CD.gt(0),f.eligible)
    for family in manifest['families']:
        for strength in [.5,1]:
            label=f'{family}__{strength:g}';assert np.isfinite(f[label]).all() and (f[label]>0).all()
            assert np.all(f[label]>=.5*f.mean8_CD-1e-12) and np.all(f[label]<=2*f.mean8_CD+1e-12)
            assert np.allclose(f.loc[~domain,label],f.loc[~domain,'mean8_CD'],atol=1e-14,rtol=0)
        assert np.allclose(f[family+'__0.5'],f.mean8_CD+.5*(f[family+'__1']-f.mean8_CD),atol=1e-14,rtol=0)
    for rule,label in freeze['selected'].items():assert np.array_equal(f[rule],f[label])
    for cycle in [1,2]:assert np.max(np.abs(f[f'cycle{cycle}_fixed__1']-f[f'cycle{cycle}_CD']))<1e-12
    assert len(f)==(242 if name=='SG_exposed' else 255)
    assert int(f.eligible.sum())==(234 if name=='SG_exposed' else 238)
    checks.append({'set':name,'rows':len(f),'eligible':int(f.eligible.sum()),'excluded':int((~f.eligible).sum()),
        'selected':freeze['selected'],'source_columns_preserved':True,'feature_row_alignment':True,'fallback_verified':True})
    frames[name]=f

expected=set()
for name,f in frames.items():
    subsets=['pooled']+list(sorted(f.airfoil.unique()))
    if f.configuration.nunique()>f.airfoil.nunique():subsets+=list(sorted(f.configuration.unique()))
    expected|={(name,c,sub,label,b) for c in ['eligible','all_complete_with_fallback'] for sub in subsets for label in labels for b in ['xlarge_CD','mean8_CD','cycle1_CD','cycle2_CD']}
observed=[(s['set'],s['cohort'],s['subset'],s['candidate'],s['baseline']) for s in results['summaries']]
assert len(observed)==len(set(observed)) and set(observed)==expected
for s in results['summaries']:
    f=frames[s['set']]
    if s['cohort']=='eligible':f=f[f.eligible]
    if s['subset']!='pooled':f=f[(f.airfoil==s['subset'])|(f.configuration==s['subset'])]
    e=(f[s['candidate']]-f.measured_CD).abs()*1e4;b=(f[s['baseline']]-f.measured_CD).abs()*1e4
    g=pd.DataFrame({'g':f.airfoil,'e':e,'b':b}).groupby('g')[['e','b']].mean()
    got={'rows':len(f),'groups':len(g),'candidate_mae_counts':e.mean(),'baseline_mae_counts':b.mean(),
        'relative_reduction_percent':100*(1-e.sum()/b.sum()),'candidate_median_counts':e.median(),'candidate_p90_counts':e.quantile(.9),
        'baseline_median_counts':b.median(),'baseline_p90_counts':b.quantile(.9),'worse_rows':int((e>b).sum()),
        'equal_rows':int((e==b).sum()),'worse_groups':int((g.e>g.b).sum()),'equal_group_relative_reduction_percent':100*(1-g.e.sum()/g.b.sum())}
    for k,x in got.items():assert np.isclose(x,s[k],atol=1e-9,rtol=1e-11),(s['set'],s['candidate'],s['subset'],k,x,s[k])
    if s['candidate'] in freeze['selected'] and s['cohort']=='eligible' and s['subset']=='pooled' and s['baseline']=='xlarge_CD':
        headline.append({k:s[k] for k in ['set','candidate','rows','candidate_mae_counts','relative_reduction_percent','worse_rows','candidate_p90_counts']})
for p,h in results['manifest']['hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
for family,record in results['manifest']['artifacts'].items():assert hashlib.sha256((EX/f'fit_{family}.pkl').read_bytes()).hexdigest()==record['sha256']
report={'metric_combinations_verified':len(observed),'cohorts':checks,'headline':headline,
    'all_recorded_input_and_model_hashes_verified':True,'no_fitting':True,
    'results_sha256':hashlib.sha256((EX/'results.json').read_bytes()).hexdigest()}
(OUT/'exposed_qa.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
