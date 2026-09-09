"""Metadata-only pin discovery and synthetic tests; no fitted-model parsing."""
import io,time,unittest
import diagnostic as d,run
def main():
    here=run.HERE;root=run.PROJECT;ledger=[]
    benchmark='submission_revision_20260908/work/renewed_research/independent_environment/inference_benchmark_plan/REGISTRY_v4.json'
    bp='b48543cc24201a161c609a08d1a1c7160db86d674becd740263bb1301d491a5e'
    r=d.parse(d.read(root/benchmark,bp,ledger),'V4 registry',ledger)
    original='model_development_20260907_risk_policy/portable/'
    manifest=original+'manifest.json';mp='706d9604d95b31f5614fc9c768e67bb3c6a84c2b7d8aa1c9f133e03c03397d82'
    m=d.parse(d.read(root/manifest,mp,ledger),'original manifest',ledger)
    roles={'prepared':'model_development_20260907_geometry_frontier/engineering/fast_inference/prepared.py','portable':original+'predictor.py','native':'model_development_20260907_risk_policy/risk_policy.py','model':original+'experimental_policies.json','references':original+'inference_references.npz'}
    inputs={benchmark:bp,manifest:mp}
    for name in ['prepared','model','references']:inputs[roles[name]]=r['scopes']['all']['files'][roles[name]]
    inputs[roles['portable']]=m['package_hashes']['predictor.py'];inputs[roles['native']]=m['producer_module_hashes'][str(root/roles['native'])]
    # Verify code only. No read of model JSON or NPZ bytes during source freeze.
    for name in ['prepared','portable','native']:d.read(root/roles[name],inputs[roles[name]],ledger)
    out=here/'synthetic_attempt_1';out.mkdir(exist_ok=False)
    stream=io.StringIO();start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromName('test_diagnostic')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    evidence={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'seconds':time.monotonic()-start,'stdout':stream.getvalue(),'actual_arrays':0,'fitted_model_JSON_parses':0}
    # Named evidence is metadata, not an actual diagnostic output directory.
    d.save(out,'DIAGNOSTICS.json',evidence)
    if not result.wasSuccessful():raise RuntimeError('synthetic failure retained; no retry')
    sources={name:d.sha((here/name).read_bytes()) for name in ['PROTOCOL.md','diagnostic.py','run.py','test_diagnostic.py','freeze.py']}
    reg={'schema':'SG_DIAGNOSTIC_SOURCE_V1','sources':sources,'inputs':inputs,'roles':roles,'members':['SG_exposed_'+k for k in d.KEYS],
      'runtime':run.runtime(),'output_allowlist':sorted(d.OUT_NAMES),'output_cap_bytes':d.CAP,'seconds':120,'workers':1,'rows':242,
      'synthetic_evidence_sha256':d.sha((out/'DIAGNOSTICS.json').read_bytes()),'source_metadata_reads':ledger,'actual_execution_authorized':False}
    raw=__import__('json').dumps(reg,sort_keys=True,indent=2,allow_nan=False).encode()
    with (here/'REGISTRY.json').open('xb') as f:f.write(raw)
    print(d.sha(raw))
if __name__=='__main__':main()
