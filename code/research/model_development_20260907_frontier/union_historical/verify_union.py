"""No-fit numerical reconciliation of frozen union weights and all panel metrics."""
import json
import numpy as np
import pandas as pd
import run_union as r

def main():
    assert (r.OUT/'report.json').exists()
    d=pd.read_csv(r.OUT/'all_row_predictions.csv',float_precision='round_trip',low_memory=False)
    label='primary_union_both';training_scores=0;maxdelta=0.;hashes=0
    for path in sorted(r.OUT.glob('weights_*.json')):
        a=json.loads(path.read_text());name=a['split'];f,idx,h=r.training(name);s=a['solutions'][label]
        assert set(a['training_nf2_row_ids'])==set(f.loc[f.context=='group','nf2_row_id'])
        w=np.array([s['weights'][c] for c in r.COMPONENTS]);assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
        error=np.abs(f[r.COMPONENTS].to_numpy()@w-f.measured_CD.to_numpy())
        for rec in s['training_panels']:
            p=rec['panel']
            if p.startswith('group_source_'):mask=(f.context=='group')&(f.source==p.removeprefix('group_source_'))
            elif p in ['group_pooled','group_equal_identity']:mask=f.context=='group'
            else:mask=f.context==(p.removesuffix('_equal_identity') if p.endswith('_equal_identity') else p.removesuffix('_pooled'))
            ix=np.flatnonzero(mask);wt=np.ones(len(ix))/len(ix)
            if p.endswith('_equal_identity'):
                counts=f.iloc[ix].group.value_counts();wt=np.array([1/(len(counts)*counts[g]) for g in f.iloc[ix].group])
            be=np.abs(f[rec['baseline']].to_numpy()-f.measured_CD.to_numpy());ratio=wt@error[ix]/(wt@be[ix])
            assert len(ix)==rec['rows'] and abs(ratio-rec['actual_ratio'])<1e-10
            training_scores+=1
        for split in (['SG_exposed','W_new_challenge'] if name=='final' else [name]):
            part=d[d.split==split];pred=part[r.COMPONENTS].to_numpy()@w
            if name=='final':
                gate=part.inference_gate.map(lambda v:str(v).lower()=='true' or v==1).to_numpy(bool);pred[~gate]=part.mean8_CD.to_numpy()[~gate]
                np.testing.assert_array_equal(part[label].to_numpy()[~gate],part.mean8_CD.to_numpy()[~gate])
            else:
                assert set(part.nf2_row_id).isdisjoint(a['training_nf2_row_ids']) and set(part.group).isdisjoint(a['training_groups'])
            delta=float(np.max(np.abs(pred-part[label].to_numpy())));maxdelta=max(maxdelta,delta);assert delta<1e-12
        for p,h in a['input_sha256'].items():assert r.sha(p)==h;hashes+=1
    def check(row,f):
        assert len(f)==row.rows
        e=np.abs(f[label].to_numpy()-f.measured_CD.to_numpy())
        for key,v in [('mae_CD',e.mean()),('median_absolute_error_CD',np.median(e)),('p90_absolute_error_CD',np.quantile(e,.9))]:assert abs(v-row[key])<1e-12
        for base in ['mean8_CD','xlarge_CD']:
            b=np.abs(f[base].to_numpy()-f.measured_CD.to_numpy());assert abs(100*(1-e.sum()/b.sum())-row[base+'_improvement_percent'])<1e-9
            assert int((e>b+1e-14).sum())==row[base+'_worse_rows']
    table=pd.read_csv(r.OUT/'panel_metrics.csv',float_precision='round_trip');assert len(table)==31
    for _,row in table.iterrows():
        p=row.panel
        if p.startswith('eligible_only/'):
            _,co,sub=p.split('/');mask=(d.split==co)&d.inference_gate.map(lambda v:str(v).lower()=='true' or v==1)
            if sub!='pooled':mask &= d['airfoil' if co=='SG_exposed' else 'configuration']==sub
        elif p.startswith('history_'):
            _,seed,source=p.split('_',2);mask=d.split.str.startswith('group_'+seed+'_')
            if source!='pooled':mask &= d.source==source
        elif p.startswith('strict_source_'):mask=d.split==p
        else:
            co='SG_exposed' if p.startswith('SG_exposed') else 'W_new_challenge';sub=p[len(co)+1:];mask=d.split==co
            if sub!='pooled':mask &= d['airfoil' if co=='SG_exposed' else 'configuration']==sub
        check(row,d[mask])
    groups=pd.read_csv(r.OUT/'identity_group_metrics.csv',float_precision='round_trip')
    for _,row in groups.iterrows():
        split,group=row.panel.split(':',1);field='airfoil' if split in ['SG_exposed','W_new_challenge'] else 'group';check(row,d[(d.split==split)&(d[field]==group)])
    for p,h in json.loads((r.OUT/'manifest.json').read_text())['hashes'].items():assert r.sha(p)==h
    r.dump(r.HERE/'validation.json',{'status':'passed','training_panel_records':training_scores,'hash_references':hashes,'max_reconstructed_prediction_difference_CD':maxdelta,'benchmark_panels':len(table),'identity_group_records':len(groups),'no_refit':True})
    print('PASS union weight reconstruction, training and31benchmark panels, group metrics and hashes',flush=True)

if __name__=='__main__':main()
