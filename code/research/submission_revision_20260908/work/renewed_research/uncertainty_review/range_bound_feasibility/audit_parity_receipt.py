"""Independent receipt/reference audit; no model imports or target member access."""
from pathlib import Path
import hashlib
import io
import json
import re
import numpy as np

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
STAGE=PROJECT/'submission_revision_20260908/work/renewed_research/model_proposal/range_bound_feasibility/stage1'
A=PROJECT/'model_development_20260907_cap_ablation'
PIN='4c80ebf2db6de68d856c4b26f83924730e087b3e36d289a8e0a92e4bab9ef397'
OPENED=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(p,h):
    p=Path(p)
    assert not p.is_symlink()
    raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==h,str(p)
    return raw
def load(p,h,keys):
    assert 'MEAS_CD' not in keys and 'measured_CD' not in keys
    with np.load(io.BytesIO(checked(p,h)),allow_pickle=False) as z:
        v={k:z[k].copy() for k in keys}
    OPENED.append({'path':str(p),'members':keys})
    return v

def main():
    out=HERE/'PARITY_RECEIPT_QA.json'
    assert not out.exists()
    impl=json.loads(checked(STAGE/'IMPLEMENTATION_FREEZE.json',PIN))
    for p,h in impl['source_sha256'].items():checked(STAGE/p,h)
    checked(STAGE.parent/'STAGE1_PROTOCOL_DRAFT.md',impl['protocol_draft_sha256'])
    receipt_path=STAGE/'precalibration/PARITY_PASS.json'
    d=json.loads(receipt_path.read_bytes())
    assert d['status']=='EXACT_PRELOSS_PARITY_PASS' and d['target_members_materialized'] is False
    assert d['execution']['implementation_sha256']==PIN and d['execution']['phase']=='parity'
    assert d['execution']['protocol_sha256']==impl['source_sha256']['PROTOCOL.md']
    assert d['execution']['scientific_protocol_sha256']==impl['protocol_draft_sha256']
    approve=json.loads(checked(STAGE/'ROOT_PARITY_APPROVAL.json',d['execution']['approval_sha256']))
    assert approve['implementation_sha256']==PIN and approve['authorized_phases']==['parity']
    assert d['topology_validated']==16 and d['stage_count']==400
    assert d['ast_sha256']['group']==impl['production_AST']['groups']
    assert d['ast_sha256']['confidence']==impl['production_AST']['confidence']
    for p,h in d['source_input_sha256'].items():checked(p,h)
    for p,h in d['artifact_sha256'].items():checked(STAGE/'precalibration'/p,h)
    assert len(d['artifact_sha256'])==34 and len(d['records'])==34
    tree_keys={'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'}
    cal_keys={'indices','nf2_row_id','X62','BASE_CD','CORE_CD_capped'}
    inf_keys={'indices','X62','BASE_CD','gate','proper_core_capped','proper_capped_full','proper_capped_half'}
    counts={'tree':0,'calibration':0,'inference':0,'inventory':0}
    for entry in d['member_access']:
        p=Path(entry['path']);keys=set(entry['materialized_members'])
        assert str(p) in d['source_input_sha256']
        assert p.suffix=='.npz' and 'MEAS_CD' not in keys and 'measured_CD' not in keys
        if re.fullmatch(r'tree_\d{2}_capped.npz',p.name):assert keys==tree_keys;counts['tree']+=1
        elif p.name.startswith('calibration_'):assert keys==cal_keys;counts['calibration']+=1
        elif keys=={'indices','gate'}:assert p.name=='inference_final.npz';counts['inventory']+=1
        else:assert keys==inf_keys;counts['inference']+=1
    assert counts=={'tree':16,'calibration':16,'inference':18,'inventory':1}
    totals={'calibration_rows_repeated':0,'inference_rows_repeated':0,'native_fallback_rows_repeated':0,'numerical_fallback_rows':0}
    contexts=set();checks=[]
    for rec in d['records']:
        context=rec['context'];kind=rec['kind'];assert rec['exact'] is True
        contexts.add(context)
        name=f'calibration_reference_{context}.npz' if kind=='calibration' else f'inference_{context}.npz'
        p=STAGE/'precalibration'/name
        v=load(p,d['artifact_sha256'][name],['indices','BASE_CD','core','anchor','gate'])
        assert len(v['BASE_CD'])==rec['rows'] and v['gate'].dtype==bool
        numerical=(v['BASE_CD']>=2.**-500)&(v['BASE_CD']<=2.**500)
        assert int((~numerical).sum())==rec['numerical_fallback']
        totals['numerical_fallback_rows']+=int((~numerical).sum())
        totals[kind+'_rows_repeated']+=len(v['BASE_CD'])
        totals['native_fallback_rows_repeated']+=int((~v['gate']).sum())
        if kind=='calibration':
            source=A/'results'/f'calibration_{context}.npz'
            z=load(source,d['source_input_sha256'][str(source)],['indices','nf2_row_id','BASE_CD','CORE_CD_capped'])
            mp=A/'results'/f'membership_{context}.json'
            m=json.loads(checked(mp,d['source_input_sha256'][str(mp)]))
            np.testing.assert_array_equal(z['indices'],m['calibration_indices'])
            np.testing.assert_array_equal(z['nf2_row_id'],m['calibration_nf2_row_ids'])
            sets=[set(m[k]) for k in ['proper_groups','calibration_groups','test_groups']]
            assert all(not sets[i]&sets[j] for i in range(3) for j in range(i))
            assert m['post_calibration_refit'] is False
            ec=z['CORE_CD_capped'];eh=z['BASE_CD']+.5*(ec-z['BASE_CD'])
        else:
            external=context in ['SG_exposed','W_new_challenge']
            source=A/('exposed_results' if external else 'results')/(f'{context}_inference.npz' if external else f'inference_{context}.npz')
            z=load(source,d['source_input_sha256'][str(source)],['indices','BASE_CD','gate','proper_capped_full','proper_capped_half'])
            ec=z['proper_capped_full'];eh=z['proper_capped_half']
            np.testing.assert_array_equal(v['gate'],z['gate']&numerical)
        np.testing.assert_array_equal(v['indices'],z['indices'])
        np.testing.assert_array_equal(v['BASE_CD'],z['BASE_CD'])
        np.testing.assert_array_equal(v['core'][v['gate']],ec[v['gate']])
        np.testing.assert_array_equal(v['anchor'][v['gate']],eh[v['gate']])
        np.testing.assert_array_equal(v['core'][~v['gate']],v['BASE_CD'][~v['gate']])
        np.testing.assert_array_equal(v['anchor'][~v['gate']],v['BASE_CD'][~v['gate']])
        checks.append({'kind':kind,'context':context,'rows':len(v['BASE_CD']),'reference_parity':'exact'})
    assert len(contexts)==18
    assert sum(r['kind']=='calibration' for r in d['records'])==16
    assert sum(r['kind']=='inference' for r in d['records'])==18
    assert {r['context']:r['rows'] for r in d['records'] if r['context'] in ['SG_exposed','W_new_challenge']}=={'SG_exposed':242,'W_new_challenge':255}
    result={'status':'PASS','implementation_sha256':PIN,'receipt_sha256':sha(receipt_path),
            'source_files_verified':len(d['source_input_sha256']),'output_files_verified':34,
            'producer_materialization_inventory':counts,'comparison_inventory':checks,'totals':totals,
            'independent_array_access':OPENED,'measured_target_members_materialized':False,
            'fitted_models_executed':False,'calibration_or_scoring_executed':False,
            'code_sha256':sha(__file__),
            'limitation':'Absence of target access is supported by authenticated source and member ledger, not an OS-level I/O trace. Mixed source-container bytes were hashed; target members were not loaded.'}
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ['status','receipt_sha256','source_files_verified','output_files_verified','producer_materialization_inventory','totals']},indent=2))

if __name__=='__main__':main()
