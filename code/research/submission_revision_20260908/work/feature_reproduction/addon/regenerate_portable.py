"""Label-free, path-relative feature reproduction. Run from any working directory."""
import argparse, hashlib, importlib.metadata, json, platform, time
from pathlib import Path
import numpy as np
import feature_math as f

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def quant(a,n):return np.array([float(f'{float(v):.{n}f}') for v in np.atleast_1d(a)])
def algebra(alpha,re,cd,cl,conf,top,bot,cm,stats):
    x9=[];x16=[];base=[]
    for i in range(len(alpha)):
        st=stats[i];c8=np.mean(cd[i]);l8=np.mean(cl[i]);sp=max(np.percentile(cd[i],90)-np.percentile(cd[i],10),1e-6)
        lr=np.log10(re[i]);lc=np.log(c8);ls=np.log(sp);a=alpha[i]
        x9.append([a,lr,st['t'],st['c'],lc,l8,ls,top[i],bot[i]])
        x16.append([a,lr,st['t'],st['tx'],st['c'],st['cx'],st['leR'],st['teA'],lc,l8,ls,conf[i],top[i],bot[i],np.log(cd[i,0])-np.log(cd[i,7]),cm[i]])
        base.append(c8)
    return f.add_features({'X9':np.array(x9),'X16':np.array(x16),'BASE_CD':np.array(base),'XLARGE_CD':cd[:,5],'all_model_CD':cd,'all_model_CL':cl})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    home=Path(__file__).resolve().parent;out=args.output.resolve();out.mkdir(exist_ok=False)
    manifest=json.loads((home/'manifest.json').read_text())
    for path,digest in manifest['files'].items():
        if '__pycache__' not in path: assert sha(home/path)==digest,path
    import aerosandbox as asb, neuralfoil
    versions={k:importlib.metadata.version(k) for k in ['numpy','aerosandbox','neuralfoil','casadi']}
    assert versions=={'numpy':'2.3.5','aerosandbox':'4.2.10','neuralfoil':'0.3.3','casadi':'3.7.2'},versions
    runtime={'python':platform.python_version(),'versions':versions,'source_sha256':{}}
    for module in [asb,neuralfoil]:
        folder=Path(module.__file__).parent
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.suffix in ['.py','.npz']:
                runtime['source_sha256'][module.__name__+'/'+str(p.relative_to(folder))]=sha(p)
    expected=json.loads((home/'expected_runtime.json').read_text())
    assert runtime==expected, 'Forward runtime version or source/weight hash mismatch'
    (out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    comparisons=[];start=time.time()
    def compare(cohort,stage,key,value,ref):
        assert value.shape==ref.shape and np.isfinite(value).all(),(cohort,stage,key)
        delta=np.abs(value-ref)
        comparisons.append({'cohort':cohort,'stage':stage,'key':key,'shape':list(value.shape),'unequal_elements':int(np.count_nonzero(value!=ref)),'max_abs_difference':float(delta.max(initial=0))})
    for name in ['historical','SG_exposed','W_new_challenge']:
        ref=load(home/'data'/f'{name}.npz');n=len(ref['alpha']);keys=ref['entry'] if name=='historical' else ref['airfoil']
        stats=[None]*n;coords={};k18=np.empty((n,18));matrices={k:np.empty((n,5)) for k in f.FIELDS}
        for entry,info in manifest['coordinates'][name].items():
            path=home/info['path'];assert sha(path)==info['sha256'];c=f.load_pts(path.read_text(errors='replace'));coords[entry]=c
            ix=np.flatnonzero(keys==entry);st=f.foil_stats2(c.tolist())
            for i in ix:stats[i]=st
            foil=asb.Airfoil(name='shape_sensitivity',coordinates=c).to_kulfan_airfoil()
            kp=foil.kulfan_parameters
            kval=np.r_[kp['upper_weights'],kp['lower_weights'],kp['leading_edge_weight'],kp['TE_thickness']]
            k18[ix]=kval
            mm=f.calc(c,ref['alpha'][ix],ref['Re'][ix])
            for k in matrices:matrices[k][ix]=mm[k]
        for k,v in matrices.items():compare(name,'transition',k,v,ref['ncrit_'+k])
        compare(name,'geometry','K18',k18,ref['K18'])
        if name=='historical':
            teacher=load(home/'data/teacher.npz');lookup={int(v):i for i,v in enumerate(teacher['nf2_row_id'])};sel=np.array([lookup[int(v)] for v in ref['nf2_row_id']])
            cd=np.column_stack([teacher['CD_'+s][sel] for s in f.SIZES]);cl=np.column_stack([teacher['CL_'+s][sel] for s in f.SIZES])
            archived=algebra(ref['alpha'],ref['Re'],cd,cl,teacher['conf_xlarge'][sel],teacher['topxtr'][sel],teacher['botxtr'][sel],teacher['cm8'][sel],stats)
            for k,v in archived.items():compare(name,'archived_teacher_algebra',k,v,ref[k])
            rawcd=np.empty((len(teacher['alpha']),8));rawcl=np.empty_like(rawcd);rawcm=np.empty_like(rawcd)
            conf=np.empty(len(rawcd));top=conf.copy();bot=conf.copy()
            for entry in sorted(coords):
                foil=asb.Airfoil(name='historical_reproduction',coordinates=coords[entry]).to_kulfan_airfoil()
                for re in np.unique(teacher['Re'][teacher['entry']==entry]):
                    ix=np.flatnonzero((teacher['entry']==entry)&(teacher['Re']==re))
                    for j,size in enumerate(f.SIZES):
                        result=foil.get_aero_from_neuralfoil(alpha=teacher['alpha'][ix],Re=float(re),mach=0.,n_crit=9,model_size=size)
                        rawcd[ix,j]=result['CD'];rawcl[ix,j]=result['CL'];rawcm[ix,j]=result['CM']
                        if size=='xlarge':conf[ix]=result['analysis_confidence'];top[ix]=result['Top_Xtr'];bot[ix]=result['Bot_Xtr']
            qcd=np.column_stack([quant(rawcd[:,j],6) for j in range(8)]);qcl=np.column_stack([quant(rawcl[:,j],5) for j in range(8)])
            # Original historical script averaged a size-by-row array.
            cm=quant(rawcm.T.mean(axis=0),5)
            fresh=algebra(ref['alpha'],ref['Re'],qcd[sel],qcl[sel],quant(conf,4)[sel],quant(top,4)[sel],quant(bot,4)[sel],cm[sel],stats)
            np.savez_compressed(out/'historical_unrounded.npz',nf2_row_id=teacher['nf2_row_id'],CD=rawcd,CL=rawcl,CM=rawcm,confidence=conf,Top_Xtr=top,Bot_Xtr=bot)
        else:
            fresh={k:np.empty_like(ref[k]) for k in ['X9','X16','BASE_CD','XLARGE_CD','all_model_CD','all_model_CL']}
            for entry,c in coords.items():
                ix=np.flatnonzero(keys==entry);a=f.predict_base(c,ref['alpha'][ix],ref['Re'][ix]);a['all_model_CD']=a.pop('all_CD');a['all_model_CL']=a.pop('all_CL')
                for k in fresh:fresh[k][ix]=a[k]
            f.add_features(fresh)
        for k,v in fresh.items():compare(name,'fresh_teacher',k,v,ref[k])
        fresh['X44']=f.supplement(fresh['X24'],matrices);fresh['K18']=k18;fresh['X62']=np.column_stack([fresh['X44'],k18]);fresh['X42']=np.column_stack([fresh['X24'],k18])
        for k in ['X44','X62']:compare(name,'fresh_combined',k,fresh[k],ref[k])
        contract44=f.supplement(ref['X24'],matrices)
        compare(name,'archived_teacher_fresh_transition','X62',np.column_stack([contract44,k18]),ref['X62'])
        np.savez_compressed(out/f'{name}.npz',**fresh,**{'ncrit_'+k:v for k,v in matrices.items()},alpha=ref['alpha'],Re=ref['Re'])
        (out/'comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
        print(name,'complete',round(time.time()-start,2),flush=True)
    result={'seconds':time.time()-start,'manifest_sha256':sha(home/'manifest.json'),'script_sha256':sha(__file__),'feature_math_sha256':sha(home/'feature_math.py'),'comparisons':comparisons,'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'complete.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
