"""Source/manifest metadata only. No NPZ/CSV materialization, export or replay."""
from pathlib import Path
import json
import integrity

HERE=Path(__file__).resolve().parent;S=HERE.parent;R=S.parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
PINS={'implementation':'b64e676833778628ca85e36a0f22d4bdb5d8ccb07f92407b6f5753bb56159773',
      'parity':'09e0d7084d000cda9683a73f2d8417c937b9599807b065c4852ed29d59630b96',
      'freeze':'9419e93aea4016d9273340d75f9252f093713e81d94d4f1e74f459d204691b85',
      'complete':'5d603bb7923853e0a21b68750cbd9f1b413e98a8cd3ee4a9ed123b58af248ad7',
      'assessment':'51234c6d1da3d0681a11a1afde4fa510dff2ba2f80762630aa8b301945d855d9'}
def main():
    inputs={};evidence={}
    def meta(path,pin):
        raw=Path(path).read_bytes()
        if integrity.sha(raw)!=pin:raise ValueError('metadata pin')
        inputs[str(path)]=pin;return json.loads(raw)
    def addmap(mapping,root=None):
        for name,h in mapping.items():inputs[str(Path(root)/name if root else Path(name))]=h
    impl=meta(S/'IMPLEMENTATION_FREEZE.json',PINS['implementation']);addmap(impl['source_sha256'],S)
    for path,pin,prefix in [(S/'precalibration/PARITY_PASS.json',PINS['parity'],S/'precalibration'),
        (S/'results/freeze.json',PINS['freeze'],S/'results'),(S/'predictions/complete.json',PINS['complete'],S/'predictions'),
        (S/'assessment/report.json',PINS['assessment'],S/'assessment')]:
        z=meta(path,pin);addmap(z.get('source_input_sha256',{}));addmap(z.get('artifact_sha256',{}),prefix);addmap(z.get('output_sha256',{}),prefix)
        evidence['certificates/'+prefix.name+'_'+path.name]=str(path)
    base=PROJECT/'model_development_20260907_cap_ablation'
    qa=meta(base/'DELIVERY_QA.json','d7d9c278bd1f34628a3302bf9620efb282a098ea49249f3cb3af712d7c5c275e')
    addmap(qa['source_and_result_sha256'])
    af=meta(base/'results/freeze.json','7d07b1beacb39de88f4c1c8b96b48ac6988c619f9e344843df3b565531c835f3')
    addmap(af['artifact_sha256'])
    ac=meta(base/'results/complete.json',inputs[str(base/'results/complete.json')]);addmap(ac['output_sha256'])
    old=S.parents[1]
    legacy=meta(old/'assessment/report.json','1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff')
    addmap(legacy['source_input_sha256']);addmap(legacy['output_sha256'])
    stage0={'sha256':{'qualified_numerics.py':'76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a',
        'STAGE0_DESIGN.md':'c7d30c08c8882f0da1342e50c0d6306a1d102798b90d8c1d747f0d874e4b719a',
        'STAGE0_CERTIFICATE.json':'8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782'},
        'independent_proof_sha256':'74d8a98f76aebc1139363b50b32d0245a6d7136a7e363b49897a5f048dcb3d23'}
    addmap(stage0['sha256'],R)
    evidence.update({'certificates/STAGE0_CERTIFICATE.json':str(R/'STAGE0_CERTIFICATE.json'),
        'certificates/STAGE0_DESIGN.md':str(R/'STAGE0_DESIGN.md'),
        'history/SERIALIZATION_ADDENDUM.md':str(S/'SERIALIZATION_ADDENDUM.md'),
        'history/SOURCE_DELTA.json':str(S/'SOURCE_DELTA.json')})
    proof=PROJECT/'submission_revision_20260908/work/renewed_research/uncertainty_review/range_bound_feasibility/STAGE0_NUMERICAL_PROOF.md'
    inputs[str(proof)]=stage0['independent_proof_sha256'];evidence['certificates/INDEPENDENT_PROOF.md']=str(proof)
    delta=meta(S/'SOURCE_DELTA.json',impl['source_sha256']['SOURCE_DELTA.json'])
    for name,h in delta['preserved_failure_sha256'].items():
        p=R/'stage1/results'/name;inputs[str(p)]=h;evidence['history/serialization_failure/'+name]=str(p)
    bundle=PROJECT/'submission_revision_20260908/work/scientific_review/bounds_portable/bundle'
    trees=meta(bundle/'manifest.json','210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea')
    for row in trees['trees']:
        if row['branch']=='proper':
            p=bundle/row['capped'];inputs[str(p)]=trees['files'][row['capped']];evidence['trees/'+row['context']+'.npz']=str(p)
    audit=PROJECT/'submission_revision_20260908/work/renewed_research/uncertainty_review/range_bound_feasibility/stage1_v2_audit'
    for name,pin in {'METRIC_QA.json':'22125eb867ab2f33157932d1e9e5091c8fc17c5532e9a3b67f064429e493a20c',
        'REVIEW.md':'fe5ef29e24f29b7df97a117da7b925629364f53d92befad82bf8a0d006003d73'}.items():
        raw=(audit/name).read_bytes()
        if integrity.sha(raw)!=pin:raise ValueError('independent audit pin')
        inputs[str(audit/name)]=pin;evidence['history/independent_audit/'+name]=str(audit/name)
    sources=['PLAN.md','integrity.py','test_integrity.py','frame_codec.py','build_replay.py','replay.py',
             'freeze_registry.py','test_replay_sources.py','PACKAGE_README.md','IMPLEMENTATION_PLAN.md','SYNTHETIC_RESULTS.md',
             'export_support.py','test_export_support.py','SUCCESSOR_TEST_FAILURE_1.md','SUCCESSOR_REVIEW.md']
    z={'status':'SOURCES_ONLY_AWAITING_REAL_EXPORT_APPROVAL','study_implementation_sha256':PINS['implementation'],
       'inputs':inputs,'evidence':evidence,'implementation_sha256':{n:integrity.sha((HERE/n).read_bytes()) for n in sources},
       'real_export_or_replay_performed':False}
    previous=meta(HERE/'drafting_snapshot_v2/REGISTRY_v2.json','203d41deeb159d139572391aa1a1e29adae99790a14279fc4d5103475078fe71')
    snapshot={}
    for name,h in previous['implementation_sha256'].items():
        raw=(HERE/'drafting_snapshot_v2'/name).read_bytes()
        if integrity.sha(raw)!=h:raise ValueError('draft snapshot mismatch')
        snapshot[name]=h
    z['preserved_drafting_snapshot_sha256']=snapshot
    z['supersedes_source_checkpoint_sha256']='203d41deeb159d139572391aa1a1e29adae99790a14279fc4d5103475078fe71'
    target=integrity.new_target(HERE/'REGISTRY_v3.json')
    with target.open('x') as f:json.dump(z,f,indent=2);f.write('\n')
    print(integrity.sha(target.read_bytes()))

if __name__=='__main__':main()
