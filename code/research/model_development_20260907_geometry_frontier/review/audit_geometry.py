"""Post-completion geometry-router audit. No LP fits and no producer writes.

Standalone process only. Authenticates old consumer archives before loading,
reconstructs geometry/prototype math independently, and checks all predictions.
"""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROUND=HERE.parent
PROJECT=ROUND.parent
FRONTIER=PROJECT/'model_development_20260907_frontier'
BRANCH=ROUND/'geometry'
OUT=BRANCH/'results'
UNION=FRONTIER/'union_historical'
VARIANTS={'geometry4':(4,.5,False),'geometry8':(8,.5,False),'geometry_condition4':(4,.5,True),'geometry8_free':(8,2.,False)}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def verify(h):
    for p,digest in h.items():assert sha(p)==digest,p
def private(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def raw_features(k,re,alpha,condition):
    return np.column_stack([k,np.log10(re),np.abs(alpha)]) if condition else k.copy()


def build(variant,k,re,alpha):
    count,radius,condition=VARIANTS[variant]
    raw=np.unique(raw_features(k,re,alpha,condition),axis=0)
    center=np.median(raw,axis=0);q=np.quantile(raw,[.25,.75],axis=0);span=q[1]-q[0]
    factors=np.r_[np.full(18,1/np.sqrt(36)),np.full(2,.5)] if condition else np.full(18,1/np.sqrt(18))
    scale=np.where(span>0,span,1);z=(raw-center)/scale;z[:,span==0]=0;z*=factors
    assert len(np.unique(z,axis=0))>=count
    chosen=[int(np.argmin(np.square(z-z.mean(axis=0)).sum(axis=1)))]
    nearest=np.square(z-z[chosen[0]]).sum(axis=1)
    for _ in range(count-1):
        index=int(np.argmax(nearest));chosen.append(index)
        nearest=np.minimum(nearest,np.square(z-z[index]).sum(axis=1))
    positive=np.sqrt(nearest[nearest>0]);h=float(np.median(positive)) if len(positive) else 1.
    return {'median':center,'scale':scale,'constant':span==0,'distance_factors':factors,
            'prototypes':z[chosen],'prototype_raw':raw[chosen],'prototype_indices':chosen,
            'bandwidth':h,'unique_raw_vectors':len(raw),'radius':radius}


def basis(m,k,re,alpha):
    raw=raw_features(k,re,alpha,VARIANTS[m['variant']][2]);constant=np.asarray(m['constant'],bool)
    z=(raw-np.asarray(m['median']))/np.asarray(m['scale']);z[:,constant]=0;z*=np.asarray(m['distance_factors'])
    d=np.square(z[:,None,:]-np.asarray(m['prototypes'])[None,:,:]).sum(axis=2)
    logits=-d/(2*m['bandwidth']**2);logits-=logits.max(axis=1,keepdims=True)
    w=np.exp(logits);w/=w.sum(axis=1,keepdims=True)
    assert np.isfinite(w).all() and (w>=0).all()
    np.testing.assert_allclose(w.sum(axis=1),1,atol=1e-14,rtol=0)
    return w


def predict(m,components,k,re,alpha,base,gate):
    row=basis(m,k,re,alpha)@np.asarray(m['corner_weights'])
    p=np.sum(components*row,axis=1)
    return np.where(gate,p,base)


def training_panels(frame):
    panels={}
    def add(name,mask,balanced=False):
        ix=np.flatnonzero(mask)
        if balanced:
            groups=frame.group.to_numpy()[ix];counts={g:int((groups==g).sum()) for g in set(groups)}
            w=np.asarray([1/(len(counts)*counts[g]) for g in groups])
        else:w=np.full(len(ix),1/len(ix))
        panels[name]=(ix,w)
    g=frame.context=='group';add('group_pooled',g);add('group_equal_identity',g,True)
    for s in sorted(frame.loc[g,'source'].unique()):add('group_source_'+s,g&(frame.source==s))
    for c in sorted(set(frame.context)-{'group'}):
        mask=frame.context==c;assert frame.loc[mask,'source'].nunique()==1
        add(c+'_pooled',mask);add(c+'_equal_identity',mask,True)
    return panels


def main():
    # This gate is deliberately before all geometry outcome reads/imports.
    assert (OUT/'freeze.json').is_file() and (OUT/'complete.json').is_file(),'Wait for 64-fit completion'
    freeze=read(OUT/'freeze.json');complete=read(OUT/'complete.json')
    assert freeze['all_64_frozen_before_exposed'] and len(freeze['model_sha256'])==complete['model_count']==64
    verify(freeze['model_sha256']);verify(complete['source_sha256']);verify(complete['evaluation_sha256'])
    prior=read(UNION/'results/manifest.json');verify(prior['hashes'])
    union=private('independent_geometry_union_archives',UNION/'run_union.py')
    native=private('independent_native_geometry_router',BRANCH/'router.py')
    d=union.loader.v2.load_data();ids=np.arange(len(d['BASE_CD']));partitions={}
    for seed in [20260906,20260908]:
        for i,test in enumerate(union.loader.v2.old.group_folds(d['group'],5,seed)):
            partitions[f'group_{seed}_fold_{i}']=(ids[~test],ids[test])
    for s in sorted(set(d['source']))+['all_uiuc_volumes']:
        test=d['source']!='stec8' if s=='all_uiuc_volumes' else d['source']==s
        train=~test&~np.isin(d['group'],d['group'][test]);partitions['strict_source_'+s]=(ids[train],ids[test])
    partitions['final']=(ids,np.array([],dtype=int))
    shaperoot=PROJECT/'model_development_20260907_transition/shape_inputs'
    sh=shaperoot/'historical.npz';expected=read(FRONTIER/'capacity/results/run_manifest.json')['hashes'];assert sha(sh)==expected[str(sh)]
    with np.load(sh) as z:
        k18=z['K18'];np.testing.assert_array_equal(z['nf2_row_id'],d['nf2_row_id'])
        np.testing.assert_array_equal(z['alpha'],d['alpha']);np.testing.assert_array_equal(z['Re'],d['Re'])
    anchorhashes=read(UNION/'results/freeze.json')['weights_sha256'];records=[]
    for split,(tr,te) in partitions.items():
        assert not set(d['group'][tr])&set(d['group'][te])
        ap=UNION/f'results/weights_{split}.json';assert sha(ap)==anchorhashes[str(ap)]
        anchor=read(ap);verify(anchor['input_sha256'])
        # Authenticate and check every saved inner context before helper assembly.
        for path in anchor['input_sha256']:
            if not path.endswith('.npz') or '_inner_' not in Path(path).name:continue
            with np.load(path,allow_pickle=False) as z:
                if 'indices' in z:np.testing.assert_array_equal(z['indices'],tr)
                else:
                    ti,vi=z['train_indices'],z['test_indices'];assert set(ti)<=set(tr) and set(vi)<=set(tr)
                    assert not set(ti)&set(vi) and not set(d['group'][ti])&set(d['group'][vi])
                    assert len(set(d['source'][vi]))==1 and not set(d['source'][ti])&set(d['source'][vi])
        f,enclosing,hashes=union.training(split);assert hashes==anchor['input_sha256'];np.testing.assert_array_equal(enclosing,tr)
        idx=f.historical_index.to_numpy(int);g=f.context.to_numpy()=='group'
        np.testing.assert_array_equal(idx[g],tr);np.testing.assert_array_equal(f.nf2_row_id,d['nf2_row_id'][idx])
        center=np.asarray([anchor['solutions']['primary_union_both']['weights'][c] for c in union.COMPONENTS])
        panels=training_panels(f);values=f[union.COMPONENTS].to_numpy();y=f.measured_CD.to_numpy()*1e4
        for variant in VARIANTS:
            path=OUT/f'{split}_{variant}.json';assert sha(path)==freeze['model_sha256'][str(path)];m=read(path)
            assert m['components']==union.COMPONENTS and m['anchor_sha256']==sha(ap)
            np.testing.assert_array_equal(m['training_nf2_row_ids'],d['nf2_row_id'][tr]);assert set(m['training_groups'])==set(d['group'][tr])
            reconstructed=build(variant,k18[tr],d['Re'][tr],d['alpha'][tr])
            for key,value in reconstructed.items():np.testing.assert_allclose(m[key],value,atol=1e-14,rtol=0,err_msg=f'{split}/{variant}/{key}')
            w=np.asarray(m['corner_weights']);assert w.shape==(VARIANTS[variant][0],27) and (w>=0).all()
            np.testing.assert_allclose(w.sum(axis=1),1,rtol=0,atol=1e-10)
            distances=np.abs(w-center).sum(axis=1);assert distances.max()<=VARIANTS[variant][1]+2e-6
            np.testing.assert_allclose(m['corner_l1_distances'],distances,atol=1e-14,rtol=0)
            pred=predict(m,values,k18[idx],d['Re'][idx],d['alpha'][idx],f.mean8_CD.to_numpy(),np.ones(len(f),bool))*1e4
            error=np.abs(pred-y);ratios=[]
            saved={(v['panel'],v['baseline']):v['actual_ratio'] for v in m['training_panels']}
            for baseline in ['xlarge_CD','mean8_CD']:
                be=abs(f[baseline].to_numpy()*1e4-y)
                for name,(ix,weight) in panels.items():
                    ratio=float(weight@error[ix]/(weight@be[ix]));ratios.append(ratio)
                    np.testing.assert_allclose(ratio,saved[name,baseline],atol=1e-10,rtol=0)
            worst=max(ratios);np.testing.assert_allclose(worst,m['actual_worst_training_ratio'],atol=1e-10,rtol=0)
            assert worst<=m['first_optimal_ratio']+1e-7+2e-6 and worst>=m['first_optimal_ratio']-2e-6
            records.append({'split':split,'variant':variant,'actual_training_worst_ratio':worst,'maximum_corner_l1':float(distances.max())})
    # Replay every complete-context outcome after all model/context checks.
    lookup={int(v):i for i,v in enumerate(d['nf2_row_id'])}
    allframe=pd.read_csv(OUT/'all_row_predictions.csv',low_memory=False);assert len(allframe)==29856
    envelope=ROUND/'envelope';cert=read(envelope/'certificate.json')
    assert sha(envelope/'row_envelope.csv')==cert['row_table_sha256'] and sha(envelope/'parsed_inputs.npz')==cert['snapshot_sha256']
    ed=pd.read_csv(envelope/'row_envelope.csv',low_memory=False)
    with np.load(envelope/'parsed_inputs.npz') as z:lower=z['predictions'].min(axis=1);upper=z['predictions'].max(axis=1)
    maxdelta=maxnative=maxbox=0.;values_checked=fallback_checked=0
    sys.path.insert(0,str(PROJECT/'model_development_20260907_transition'));import shape_inputs
    for split in allframe.split.unique():
        f=allframe[allframe.split==split];ex=split in ['SG_exposed','W_new_challenge']
        snapshot=BRANCH/('exposed_results' if ex else 'results')/(f'{split}_predictions.csv' if ex else f'predictions_{split}.csv')
        separate=pd.read_csv(snapshot,low_memory=False)
        assert len(separate)==len(f)
        if not ex:np.testing.assert_array_equal(separate.nf2_row_id,f.nf2_row_id)
        for key in ['Re','alpha','measured_CD']+list(VARIANTS):np.testing.assert_allclose(separate[key],f[key],atol=1e-13,rtol=0)
        ep=ed[ed.split==split]
        if ex:
            shape=shaperoot/f'{split}.npz';assert sha(shape)==expected[str(shape)]
            with np.load(shape) as z:
                geom=z['K18'];np.testing.assert_allclose(z['Re'],f.Re,atol=1e-13,rtol=0);np.testing.assert_allclose(z['alpha'],f.alpha,atol=1e-13,rtol=0)
            native_inputs=shape_inputs.load_exposed(split);base=native_inputs['BASE_CD']
            assert all(str(v).lower() in ['true','false'] for v in f.inference_gate)
            gate=np.asarray([str(v).lower()=='true' for v in f.inference_gate],dtype=bool)
            assert len(gate)=={'SG_exposed':242,'W_new_challenge':255}[split] and gate.sum()=={'SG_exposed':234,'W_new_challenge':238}[split]
        else:
            ix=np.asarray([lookup[int(v)] for v in f.nf2_row_id]);geom=k18[ix];base=d['BASE_CD'][ix];gate=np.ones(len(f),bool)
            assert set(ix)==set(partitions[split][1]);ep=ep.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
        for key in ['Re','alpha','measured_CD']:np.testing.assert_allclose(ep[key],f[key],atol=1e-13,rtol=0)
        envelope_ids=ep.context_row_index.to_numpy(int)
        for variant in VARIANTS:
            m=read(OUT/f"{'final' if ex else split}_{variant}.json")
            if not ex:assert set(f.group).isdisjoint(m['training_groups'])
            components=f[m['components']].to_numpy();re=f.Re.to_numpy();alpha=f.alpha.to_numpy()
            p=predict(m,components,geom,re,alpha,f.mean8_CD.to_numpy(),gate)
            maxdelta=max(maxdelta,float(abs(p-f[variant]).max()));values_checked+=len(p)
            produced=native.predict(m,components,geom,re,alpha,base,gate)
            independent=predict(m,components,geom,re,alpha,base,gate)
            maxnative=max(maxnative,float(abs(produced-independent).max()))
            np.testing.assert_array_equal(produced[~gate],base[~gate]);fallback_checked+=int((~gate).sum())
            excess=np.maximum(lower[envelope_ids]-p,p-upper[envelope_ids]);maxbox=max(maxbox,float(excess.max()))
    assert len(records)==64 and values_checked==119424 and fallback_checked==100
    assert maxdelta<1e-12 and maxnative<1e-12 and maxbox<1e-12
    verify(freeze['model_sha256']);verify(complete['source_sha256']);verify(complete['evaluation_sha256'])
    result={'status':'PASS','router_models':64,'prediction_values':values_checked,'native_fallback_values':fallback_checked,
            'max_saved_prediction_difference_CD':maxdelta,'max_independent_native_difference_CD':maxnative,
            'max_envelope_violation_CD_with_1e_12_tolerance':maxbox,'records':records,
            'scope':'Checks saved feasible solutions and scores, NOT optimizer optimality; envelope rounding tolerance distinct from exact certificate.',
            'geometry_complete_sha256':sha(OUT/'complete.json'),'audit_code_sha256':sha(Path(__file__))}
    (HERE/'geometry_audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='records'})


if __name__=='__main__':main()
