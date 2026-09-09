"""Recompute all selectors from saved predictions, never refit."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import run_kernel as r

def main():
    d=r.inputs.load_historical();report=[]
    paths=sorted(r.OUT.glob('*_inner_group.npz'))
    assert len(paths)==16
    for path in paths:
        name=path.stem.removesuffix('_inner_group');a=np.load(path);idx=a['indices'];assert len(set(idx))==len(idx)
        prior=np.load(r.C3/'results'/path.name);np.testing.assert_array_equal(idx,prior['indices'])
        for c in r.CONTROLS:np.testing.assert_array_equal(a[c],prior[c])
        f=pd.DataFrame({'y':d['MEAS_CD'][idx],'group':d['group'][idx],'source':d['source'][idx]})
        scores={}
        for c in r.LABELS:
            e=np.abs(a[c]-f.y.to_numpy());ratios={}
            for b,key in [('mean8','BASE_CD'),('xlarge','XLARGE_CD')]:
                be=np.abs(d[key][idx]-f.y.to_numpy());ratios[b+':pooled']=e.sum()/be.sum()
                for source in f.source.unique():
                    mask=f.source.to_numpy()==source;ratios[b+':source_'+source]=e[mask].sum()/be[mask].sum()
                agg=pd.DataFrame({'e':e,'b':be,'g':f.group}).groupby('g')[['e','b']].mean()
                ratios[b+':equal_group']=agg.e.sum()/agg.b.sum()
            scores[c]=ratios
        nt=0
        for p in sorted(r.OUT.glob(name+'_inner_transfer_*.npz')):
            z=np.load(p);tr=z['train_indices'];te=z['test_indices'];source=p.stem.rsplit('_',1)[1]
            assert set(tr)<=set(idx) and set(te)<=set(idx) and set(d['group'][tr]).isdisjoint(d['group'][te])
            old=np.load(r.C3/'results'/p.name)
            for key in ['train_indices','test_indices']+r.CONTROLS:np.testing.assert_array_equal(z[key],old[key])
            for c in r.LABELS:
                e=np.abs(z[c]-d['MEAS_CD'][te])
                for b,key in [('mean8','BASE_CD'),('xlarge','XLARGE_CD')]:scores[c][b+':transfer_'+source]=e.sum()/np.abs(d[key][te]-d['MEAS_CD'][te]).sum()
            nt+=1
        log=json.loads((r.OUT/('freeze.json' if name=='final' else 'log_'+name+'.json')).read_text());best=None;bw=np.inf;bp=np.inf
        for row in log['selection']['candidate_scores']:
            c=row['candidate'];computed=scores[c];assert set(computed)==set(row['ratios'])
            for k,v in computed.items():assert abs(v-row['ratios'][k])<1e-12
            worst=max(computed.values());pooled=(computed['mean8:pooled']+computed['xlarge:pooled'])/2
            assert abs(worst-row['worst_ratio'])<1e-12
            if worst<bw-1e-12 or (abs(worst-bw)<=1e-12 and pooled<bp-1e-12):best,bw,bp=c,worst,pooled
        assert best==log['selected']
        report.append({'split':name,'selected':best,'source_contexts':nt,'all_ratios_verified':True})
    r.dump(Path(__file__).parent/'inner_validation.json',{'status':'passed','splits':report,'no_refit':True});print('PASS16 exact selector reconstructions')

if __name__=='__main__':main()
