"""No-fit historical input and spawn-registry audit; writes only this folder."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import hashlib
import json
import multiprocessing as mp
import sys
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
sys.path.insert(0,str(ROOT))
import run_transition as adapter


def worker_registry():
    return {'families':adapter.common.FAMILIES,'labels':adapter.common.LABELS,
        'fit_module':adapter.common.fit.__module__,'predict_module':adapter.common.predict.__module__,
        'original_fit_module':adapter.ORIGINAL_FIT.__module__,
        'original_predict_module':adapter.ORIGINAL_PREDICT.__module__}


def main():
    old=adapter.common.v2.load_data();d=adapter.inputs.load_historical()
    for key in old:assert np.array_equal(old[key],d[key]),key
    assert d['X42'].shape==(8371,42) and d['X62'].shape==(8371,62)
    assert np.array_equal(d['X42'][:,:24],old['X24']) and np.array_equal(d['X62'][:,:44],d['X44'])
    assert np.array_equal(d['X42'][:,24:],d['K18']) and np.array_equal(d['X62'][:,44:],d['K18'])
    assert np.isfinite(d['K18']).all() and np.isfinite(d['X44']).all()
    with np.load(ROOT/'inputs/historical.npz',allow_pickle=False) as z:
        assert np.array_equal(z['row_id'],np.arange(8371)) and np.array_equal(z['nf2_row_id'],d['nf2_row_id'])
        assert np.array_equal(z['alpha'],d['alpha']) and np.array_equal(z['Re'],d['Re'])
        assert np.array_equal(z['ncrit_grid'],[5,7,9,11,13])
        reference={'ncrit_CD':d['XLARGE_CD'],'ncrit_CL':d['all_model_CL'][:,5],
            'ncrit_confidence':d['X16'][:,11],'ncrit_Top_Xtr':d['X16'][:,12],'ncrit_Bot_Xtr':d['X16'][:,13]}
        for key,target in reference.items():assert np.max(np.abs(z[key][:,2]-target))<=1e-12,key
        extra=[]
        for j in [0,1,3,4]:
            extra.append(np.log(z['ncrit_CD'][:,j]/z['ncrit_CD'][:,2]))
            for key in ['ncrit_CL','ncrit_confidence','ncrit_Top_Xtr','ncrit_Bot_Xtr']:extra.append(z[key][:,j]-z[key][:,2])
        assert np.array_equal(np.column_stack([old['X24']]+extra),d['X44'])
    for entry in np.unique(d['entry']):assert len(np.unique(d['K18'][d['entry']==entry],axis=0))==1
    parent=worker_registry()
    with ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn')) as pool:
        child=pool.submit(worker_registry).result(timeout=60)
    assert child==parent and len(parent['families'])==7 and len(parent['labels'])==16
    helper=adapter.common.v2.OLD/'reproduction/reproduce_doubleclean.py'
    digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    links=[]
    prior_manifest=adapter.common.v2.ROOT/'external_results/pre_score_manifest.json'
    m=json.loads(prior_manifest.read_text());assert m['hashes'][str(helper)]==digest
    links.append({'manifest':str(prior_manifest),'helper_sha256':m['hashes'][str(helper)],'matches':True})
    cycle3=ROOT.parent/'model_development_20260907_search/results/run_manifest.json'
    m3=json.loads(cycle3.read_text())
    assert str(helper) not in m3['hashes']
    for p,h in m3['hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    report={'historical_rows':8371,'historical_groups':93,'all_original_arrays_exactly_preserved':True,
        'central_ncrit9_all_five_fields_verified':True,'X44_formula_exact':True,'shape_row_alignment_verified':True,
        'parent_registry':parent,'spawned_registry':child,'no_fitting_performed':True,
        'provenance_supplement':{'helper_path':str(helper),'current_sha256':digest,
            'previous_hash_links':links,'Cycle3_manifest_omits_helper':True,'all_Cycle3_recorded_hashes_unchanged':True,
            'scope':'Supplement recorded during Cycle4 running; not misrepresented as a before-fit amendment.'}}
    (OUT/'preflight_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
