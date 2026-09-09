"""Final exact cross-check and hash witness; no fitting and no tolerance changes."""
import hashlib,json,pathlib,re,sys
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def main():
    c=read(ROOT/'connected_attempt_1/private_reproduction/reproduced/report.json')
    r=read(ROOT/'reference_attempt_1/complete.json')
    assert c['status']==r['status']=='PASS'
    assert r['Hist_fits']==120 and r['policy_fits']==16 and r['LP_solves']==32
    counts={'A_core_fits':96,'A_calibrators':48,'B_inner_core_fits':48,'B_scale_fits':16,'B_calibrators':16,'panels':31,'procedures':22}
    assert all(c.get(k)==v for k,v in counts.items())
    assert c['native_array_parity']==c['calibrator_parity']=='exact'
    bridge=read(ROOT/'matched_bridge.json');assert bridge['bridge']['status']=='PASS'
    assert bridge['bridge']['feature_parity']['comparisons']==55
    feat=read(ROOT/'matched_feature_results/complete.json')
    for name,h in feat['outputs'].items():assert sha(ROOT/'matched_feature_results'/name)==h
    assert read(ROOT/'connected_attempt_1/failure.json')['status']=='FAIL'
    for folder,record in [('reference_attempt_1',r)]:
        for name,h in record['output_sha256'].items():assert sha(ROOT/folder/name)==h,name
    refroot=ROOT/'reference_extraction/reference_reproduction';fresh=ROOT/'reference_attempt_1'
    checks=[]
    for p in sorted(fresh.glob('*.npz')):
        a,b=load(p),load(refroot/'results'/p.name)
        assert a.keys()==b.keys()
        for k in a:assert np.array_equal(a[k],b[k]),(p.name,k)
        checks.append({'file':p.name,'keys':list(a),'exact':True})
    for p in fresh.glob('policy_*.json'):assert read(p)==read(refroot/'results'/p.name)
    sys.path.insert(0,str(refroot));import replay
    refs=load(refroot/'evaluation/reference_predictions.npz');ev=read(refroot/'evaluation/manifest.json');rows=0
    for name,pos in ev['positions'].items():
        suffix='_final.npz' if name in ['SG_exposed','W_new_challenge'] else '_outer.npz'
        a=load(fresh/(name+suffix));rows+=len(pos)
        for label,key in [('unpenalized_transfer','prediction'),('half_strength','half')]:assert np.array_equal(replay.csv_roundtrip(a[key]),refs[label][pos])
    assert rows==29856
    testcounts={}
    paths={'bounds':ROOT/'bounds_tests.log','reference':ROOT/'reference_tests.log','wrapper':ROOT/'wrapper_tests.log',
      'feature':ROOT/'matched_feature_tests.log','correction':ROOT/'standalone_correction_tests.log'}
    for key,p in paths.items():
        text=p.read_text();m=re.search(r'Ran (\d+) tests?',text);assert m and '\nOK' in text
        testcounts[key]=int(m.group(1))
    assert testcounts=={'bounds':6,'reference':4,'wrapper':7,'feature':4,'correction':33}
    runtime=read(ROOT/'matched_feature_results/runtime.json')
    prior_witness=ROOT.parents[2]/'deliverables/NeuralFoil_Private_Submission_Package_v2/reproduction/connected/execution/fresh_wrapper_complete.json'
    prior=read(prior_witness);prior_root=pathlib.Path('/private/tmp/nf-connected-reviewer-uTBUMh/attempt')
    prior_checks=[]
    for name,h in prior['output_sha256'].items():
        if name.startswith('private_reproduction/reproduced/') and not name.endswith('report.json'):
            p=prior_root/name;assert sha(p)==h
            new=ROOT/'connected_attempt_1'/name
            if p.suffix=='.npz':
                a,b=load(p),load(new);assert a.keys()==b.keys()
                for k in a:assert np.array_equal(a[k],b[k]),(name,k)
            prior_checks.append({'file':name,'prior_sha256':h,'new_sha256':sha(new),'byte_identical':sha(new)==h})
    result={'status':'PASS_STAGED_MATCHED_BUILD_CHAIN_WITH_PRESERVED_PYPI_FAILURE','new_third_party_environments':3,'inherited_site_packages':False,'same_OS_hardware':True,'matched_forward_interpreter_fresh_from_distribution':True,
      'independent_investigator':False,'new_statistical_validation':False,'fixed_model_objects_refitted':280,'calibrators_and_policies':80,
      'tests':testcounts,'exact_bounds_comparisons':80,'staged_chain_counts':counts,'reference_Hist_fits':120,'reference_policy_fits':16,
      'reference_fresh_arrays_exact':checks,'reference_evaluation_rows_each':rows,'reference_columns':2,
      'feature_runtime_source_hashes':len(runtime['source_sha256']),'matched_bridge_sha256':sha(ROOT/'matched_bridge.json'),'standalone_correction_report_sha256':sha(ROOT/'connected_attempt_1/private_reproduction/reproduced/report.json'),
      'reference_complete_sha256':sha(ROOT/'reference_attempt_1/complete.json'),
      'standalone_output_sha256':{str(p.relative_to(ROOT/'connected_attempt_1/private_reproduction/reproduced')):sha(p) for p in sorted((ROOT/'connected_attempt_1/private_reproduction/reproduced').rglob('*')) if p.is_file()},
      'preserved_original_descriptive_flags':'Frozen component scripts hardcode same-environment flags. Those original literal strings are not provenance-aware; this separately recorded provisioning witness establishes fresh third-party installations, not a new OS or interpreter build.',
      'root_file_sha256':{p.name:sha(p) for p in sorted(ROOT.iterdir()) if p.is_file()},
      'bounds_verification_sha256':sha(ROOT/'bounds_replay.log')}
    result['prior_successful_correction_outputs']=prior_checks
    result['prior_wrapper_witness_sha256']=sha(prior_witness)
    with (ROOT/'VERIFIED.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ['reference_fresh_arrays_exact','root_file_sha256']},indent=2))
if __name__=='__main__':main()
