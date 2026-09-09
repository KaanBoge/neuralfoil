"""Independent direct relation checks; materializes X62 only, never BASE_CD."""
from pathlib import Path
import hashlib,json,io,zipfile,csv,time,traceback
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=ROOT/'model_proposal/feature_relation_guard_audit'
PIN='98dad2fb1b58ccc564433bd674634cd395d84a845cdee78140d7445b65da7fd2'
def checked(p,h):
    p=Path(p);assert not any(x.is_symlink() for x in (p,*p.parents));raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==h,str(p);return raw
def main():
    start=time.monotonic();rec=json.loads(checked(P/'results/COMPLETE.json',PIN))
    app=json.loads(checked(P/'ROOT_EXECUTION_APPROVAL.json','09e68b7792d727a67866c8079b841547654a1021f486cfe8be6b0bf0edff565c'))
    assert app['implementation_sha256']==rec['implementation_sha256'] and 'feature_guard_audit' in app['authorized_phases']
    freeze=json.loads(checked(P/'IMPLEMENTATION_FREEZE.json',rec['implementation_sha256']))
    for n,h in freeze['source_sha256'].items():checked(P/n,h)
    checked(ROOT/'feature_relation_certification/relations.py',freeze['relations_sha256']);checked(ROOT/'feature_relation_certification/FEATURE_GUARD_AUDIT_PLAN.md',freeze['plan_sha256'])
    for n,h in rec['outputs'].items():checked(P/'results'/n,h)
    data=ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1'
    manifest=json.loads(checked(data/'manifest.json',freeze['manifest_sha256']))
    buffers={}
    for n,(h,size) in freeze['fixed_payloads'].items():
        assert manifest['files'][n]=={'sha256':h,'bytes':size};buffers[n]=checked(data/n,h);assert len(buffers[n])==size
    with zipfile.ZipFile(io.BytesIO(buffers['features/X62.npz'])) as z:
        infos=z.infolist();assert len(infos)==2 and {i.filename for i in infos}=={'X62.npy','BASE_CD.npy'};assert sum(i.file_size for i in infos)<=8*1024*1024
    with np.load(io.BytesIO(buffers['features/X62.npz']),allow_pickle=False) as z:X=z['X62'].copy()
    assert X.dtype==np.float64 and X.shape==(8868,62)
    # Independent vector equations; no call to producer/pure relation guard.
    finite=np.isfinite(X).all(axis=1);absolute=X[:,16]==np.abs(X[:,0]);minimum=X[:,18]==np.minimum(X[:,12],X[:,13]);maximum=X[:,19]==np.maximum(X[:,12],X[:,13]);guard=finite&absolute&minimum&maximum
    expected={'all_finite':finite,'absolute_equal':absolute,'minimum_equal':minimum,'maximum_equal':maximum,'guard':guard}
    rows=list(csv.DictReader(io.StringIO(checked(P/'results/rows.csv',rec['outputs']['rows.csv']).decode())))
    assert len(rows)==8868
    for i,row in enumerate(rows):
        assert int(row['index'])==i
        for k,v in expected.items():assert row[k] in ['True','False'] and (row[k]=='True')==bool(v[i])
    pairs=json.loads(buffers['features/maps.json'],object_pairs_hook=lambda pairs:pairs);assert len(pairs)==34
    maps=dict(pairs);assert len(maps)==34
    contexts=[f'group_{s}_fold_{i}' for s in [20260906,20260908] for i in range(5)]+['strict_source_stec8','strict_source_vol1','strict_source_vol2','strict_source_vol3','strict_source_all_uiuc_volumes','final']
    assert set(maps)=={'calibration/'+c for c in contexts}|{'native/'+c for c in contexts+['SG_exposed','W_new_challenge']}
    counts=json.loads(checked(P/'results/counts.json',rec['outputs']['counts.json']));assert set(counts)=={'master'}|set(maps)
    repeated=0
    for name,ix in [('master',list(range(8868)))]+list(maps.items()):
        assert all(type(i) is int and 0<=i<8868 for i in ix);failed=[i for i in ix if not guard[i]]
        direct={'row_instances':len(ix),'unique_indices':len(set(ix)),'pass_instances':len(ix)-len(failed),'failed_instances':len(failed),'violating_indices_in_original_order':failed,'nonfinite_indices_in_original_order':[i for i in ix if not finite[i]]}
        assert counts[name]==direct;repeated+=len(ix) if name!='master' else 0
    ledger=rec['actual_materializations'];assert len(ledger)==2 and ledger[0]['member']=='X62' and ledger[1]['operation']=='JSON map parse'
    assert rec['end_authentication'] is True and guard.all()
    for n,h in rec['outputs'].items():checked(P/'results'/n,h)
    return {'status':'PASS','complete_sha256':PIN,'rows':8868,'boolean_checks':44340,'mapped_contexts':34,'mapped_row_instances':repeated,'summary_entries':35,'failures':0,'materialized_NPZ_members':['X62'],'seconds':time.monotonic()-start,'scope':'retained feature compliance only; no BASE_CD/targets/tree/prediction/calibration; not arbitrary caller proof'}
if __name__=='__main__':
    out=HERE/'FEATURE_GUARD_RESULT_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'FEATURE_GUARD_RESULT_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
