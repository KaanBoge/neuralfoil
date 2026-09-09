from pathlib import Path
import hashlib,json,io
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;R=HERE.parent/'reference_reproduction'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def eq(a,b):np.testing.assert_array_equal(a,b)
def csv(a):return pd.read_csv(io.StringIO(pd.DataFrame({'value':a}).to_csv(index=False))).value.to_numpy()
def main():
    manifest_counts={}
    for name in ['source_manifest.json','input_manifest.json','release_manifest.json']:
        m=read(R/name)
        for p,h in m['files'].items():assert sha(R/p)==h
        manifest_counts[name]=len(m['files'])
    inp=read(R/'input_manifest.json');co=read(R/'results/complete.json');fr=read(R/'results/freeze.json')
    for p,h in co['output_sha256'].items():assert sha(R/'results'/p)==h
    assert sha(R/'results/freeze.json')==co['freeze_sha256']
    assert fr['external_inference_started'] is False
    for p,h in fr['policy_sha256'].items():assert sha(R/'results'/p)==h
    d=load(R/'data/historical.npz');allidx=np.arange(8371);transfer=0;archives=0;drift=[]
    for context in inp['contexts']:
        m=read(R/'memberships'/f'{context}.json');tr=np.array(m['train']);te=np.array(m['test'],dtype=int)
        assert not(set(d['group'][tr]) & set(d['group'][te]))
        if context.startswith('group_'):
            _,seed,_,fold=context.split('_');names=np.array(sorted(set(d['group'])));np.random.default_rng(int(seed)).shuffle(names)
            eq(te,allidx[np.isin(d['group'],names[int(fold)::5])])
        elif context!='final':
            src=context.removeprefix('strict_source_');mask=d['source']!='stec8' if src=='all_uiuc_volumes' else d['source']==src
            eq(te,allidx[mask]);eq(tr,allidx[~mask & ~np.isin(d['group'],d['group'][mask])])
        g=load(R/'results'/f'{context}_group.npz');ref=load(R/'references'/f'{context}_inner_group.npz');eq(g['indices'],tr);eq(g['core'],ref['core']);archives+=1
        for src in sorted(set(d['source'][tr])):
            test=tr[d['source'][tr]==src];train=tr[(d['source'][tr]!=src)&~np.isin(d['group'][tr],d['group'][test])]
            if len(set(d['group'][train]))<6 or len(train)<300:continue
            a=load(R/'results'/f'{context}_transfer_{src}.npz');b=load(R/'references'/f'{context}_inner_transfer_{src}.npz')
            eq(a['train'],train);eq(a['test'],test)
            for key in ['train','test','core']:eq(a[key],b[key])
            transfer+=1;archives+=1
        assert read(R/'results'/f'policy_{context}.json')==m['policy_reference']
        if context!='final':
            a=load(R/'results'/f'{context}_outer.npz');b=load(R/'references'/f'{context}_outer.npz')
            eq(csv(a['native_core']),a['serialized_core']);eq(a['serialized_core'],b['core_csv'])
            for key in ['prediction','strength','half']:eq(csv(a[key]),b[key+'_csv'])
            drift.append(float(abs(a['native_core']-a['serialized_core']).max()))
    ev=read(R/'evaluation/manifest.json');refs=load(R/'evaluation/reference_predictions.npz');assert sha(R/'evaluation/reference_predictions.npz')==ev['reference_sha256']
    positions=[]
    for context,pos in ev['positions'].items():
        external=context in ['SG_exposed','W_new_challenge'];a=load(R/'results'/(context+('_final.npz' if external else '_outer.npz')))
        positions.extend(pos)
        for label,key in [('unpenalized_transfer','prediction'),('half_strength','half')]:eq(csv(a[key]),refs[label][pos])
    eq(np.sort(positions),np.arange(29856))
    native=0
    for context in ['historical','SG_exposed','W_new_challenge']:
        a=load(R/'results'/f'{context}_final.npz');b=load(R/'references'/f'{context}_final.npz')
        eq(a['core'],b['CORE_CD']);eq(a['prediction'],b['prediction']);native+=len(a['core'])
        if context!='historical':
            data=load(R/'data'/f'{context}.npz');assert 'MEAS_CD' not in data
            for key in ['prediction','half']:eq(a[key][~a['gate']],data['BASE_CD'][~a['gate']])
    assert transfer==56 and archives==72 and native==8868
    assert co['counts']==dict(enclosing=16,group_inner=48,transfer_inner=56,policies=16)
    result={'status':'PASS','manifest_file_counts':manifest_counts,'enclosing_fits':16,'group_inner_fits':48,'transfer_inner_fits':56,'all_Hist_fits':120,'inner_fits':104,'inner_archives':72,'policies':16,'LP_solves_by_code':32,'evaluation_rows_each_reference':29856,'reference_columns':2,'native_final_rows':8868,'max_native_to_CSV_core_drift':max(drift),'source_hashes':{str(p.relative_to(R)):sha(p) for p in [R/'replay.py',R/'results/complete.json',R/'results/freeze.json',R/'extraction_verified.json']},'scope':'Read-only authenticated output and role arithmetic checks; no fitting or accuracy recomputation.'}
    (HERE/'REFERENCE_REPLAY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
