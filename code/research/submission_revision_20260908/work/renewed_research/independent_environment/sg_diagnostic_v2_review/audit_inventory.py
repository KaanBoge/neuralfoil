"""Receipt/layout/hex-inventory audit only. Never reads model JSON or NPZ input bytes."""
from pathlib import Path
import hashlib,json,math,struct

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parents[1]
PROJECT=RESEARCH.parents[2]
BASE=RESEARCH/'model_proposal/inference_benchmark_diagnosis/v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p,pin):
    assert sha(p)==pin,str(p)
    return json.loads(p.read_text())
def ordered(x):
    n=struct.unpack('>Q',struct.pack('>d',x))[0]
    return (~n)&((1<<64)-1) if n>>63 else n|(1<<63)
def main():
    r=read(BASE/'REGISTRY.json','43beec6c6cf19268b3876c4e7b3138aea570eee949b7ef1b99779530769a78aa')
    ap=read(BASE/'ROOT_ACTUAL_APPROVAL.json','240804f728a1696768bfb76306fbaa1c6415606f03c82837dc0f0f9483fe3c85')
    out=BASE/'actual_attempt_1'
    c=read(out/'COMPLETE.json','3bcf490bba59c26d871a09d1cda641280a3852fdbb3cc5dd0bbb7afb180e432f')
    assert set(p.name for p in out.iterdir())==set(c['outputs'])|{'COMPLETE.json'}
    records={name:read(out/name,h) for name,h in c['outputs'].items()}
    diag=records['DIAGNOSTICS.json'];ledger=records['ACCESS.json'];attempt=records['ATTEMPT.json']
    expected=dict(actual_execution_authorized=True,entrypoint_sha256=r['sources']['run.py'],
                  members=r['members'],output_cap_bytes=8*2**20,output_path=str(out),
                  phase='sg_reference_diagnostic',registry_sha256=sha(BASE/'REGISTRY.json'),
                  rows=242,runtime=r['runtime'],seconds=120,workers=1)
    assert ap==expected
    assert c['approval_sha256']==sha(BASE/'ROOT_ACTUAL_APPROVAL.json')
    assert c['registry_sha256']==sha(BASE/'REGISTRY.json')
    assert c['runtime']==r['runtime']==attempt['runtime']
    assert c['status']=='COMPLETE_DIAGNOSTIC_INVENTORY_ONLY'
    assert [c[k] for k in ('NPZ_materializations','inference_calls','benchmark_timings','fits','rows')]==[6,3,0,0,242]
    for key,value in attempt.items():assert c[key]==value,key
    for name,pin in r['sources'].items():assert sha(BASE/name)==pin,name
    first_parse=next(i for i,e in enumerate(ledger) if e.get('identity')=='model JSON')
    execution=[(i,e) for i,e in enumerate(ledger) if e['operation']=='source buffer execution']
    assert len(execution)==3
    for name,pin in r['inputs'].items():
        indexes=[i for i,e in enumerate(ledger) if e['operation']=='authenticated bytes' and e.get('path')==str(PROJECT/name) and e['sha256']==pin]
        assert len(indexes)==2 and indexes[0]<first_parse and indexes[1]>execution[-1][0],name
        # Only Python source and provenance manifests are reread. Model/NPZ payloads excluded.
        if name.endswith('.py') or name.endswith('/manifest.json') or name.endswith('/REGISTRY_v4.json'):
            assert sha(PROJECT/name)==pin,name
    members=[e for e in ledger if e['operation']=='NPZ member materialization']
    assert [e['member'] for e in members]==r['members'] and len(members)==6
    assert all(e['archive_sha256']==r['inputs'][r['roles']['references']] for e in members)
    assert [e['sha256'] for _,e in execution]==[r['inputs'][r['roles'][k]] for k in ('prepared','portable','native')]
    wanted={'native_policy_saved_core_vs_archived_CD','portable_vs_archived_native_CD','prepared_core_vs_saved_core',
            'prepared_vs_archived_native_CD','prepared_vs_native_policy_features','prepared_vs_native_policy_strength',
            'prepared_vs_portable_CD','prepared_vs_portable_c','prepared_vs_portable_f','prepared_vs_portable_phi',
            'prepared_vs_portable_raw','prepared_vs_portable_strength','prepared_vs_portable_z','redundant_full_strength_expression'}
    comp=diag['comparisons'];assert set(comp)==wanted
    nonexact={k for k in comp if 'archived' in k};assert len(nonexact)==3
    rows=[]
    for name,x in comp.items():
        assert x['same_shape_dtype'] and x['actual']['dtype']==x['expected']['dtype']=='float64'
        cells=x['different_cells'];assert len(cells)==x['different_count']
        positions=[tuple(v['index']) for v in cells];assert len(set(positions))==len(positions)
        for v in cells:
            assert len(v['index'])==len(x['actual']['shape'])
            assert all(type(i) is int and 0<=i<n for i,n in zip(v['index'],x['actual']['shape']))
            a,b=float.fromhex(v['actual_hex']),float.fromhex(v['expected_hex'])
            assert math.isfinite(a) and math.isfinite(b) and a>0 and b>0
            assert v['absolute_difference']==abs(a-b) and v['ULPs']==abs(ordered(a)-ordered(b))
        assert x['max_abs']==max((v['absolute_difference'] for v in cells),default=0.)
        assert x['max_ULPs']==max((v['ULPs'] for v in cells),default=0)
        if name in nonexact:
            assert len(cells)==22 and x['max_ULPs']==1 and x['max_abs']==6.938893903907228e-18
            assert not x['numerically_equal'] and not x['bitwise_equal']
        else:
            assert not cells and x['numerically_equal'] and x['bitwise_equal']
            assert x['actual']['sha256_C_value_bytes']==x['expected']['sha256_C_value_bytes']
        rows.append({'comparison':name,'different_cells':len(cells),'bitwise_equal':x['bitwise_equal'],'max_abs':x['max_abs'],'max_ULPs':x['max_ULPs']})
    inventory=[comp[name]['different_cells'] for name in sorted(nonexact)]
    assert inventory[0]==inventory[1]==inventory[2]
    layout=diag['locals_original_layout']
    assert layout['prepared']==layout['portable']
    for native,prepared in [('c','c'),('features','f'),('pred','pred'),('strength','strength')]:
        assert layout['native'][native]==layout['prepared'][prepared]
    assert layout['prepared']['c']==diag['inputs']['CORE_CD']
    assert diag['false_gate_fallback_exact'] is True and diag['input_immutability_exact'] is True
    total=sum(p.stat().st_size for p in out.iterdir());assert total<7*2**20
    result={'status':'PASS_RECEIPT_AND_INVENTORY_AUDIT_NOT_ARRAY_REPLAY',
            'completion_sha256':sha(out/'COMPLETE.json'),'diagnostics_sha256':sha(out/'DIAGNOSTICS.json'),
            'source_registry_sha256':sha(BASE/'REGISTRY.json'),'approval_sha256':sha(BASE/'ROOT_ACTUAL_APPROVAL.json'),
            'output_bytes':total,'access_records':len(ledger),'comparisons':rows,
            'different_row_indices':[v['index'][0] for v in inventory[0]],
            'inference_reruns':0,'real_array_or_fitted_model_payloads_read':0,
            'input_start_end_authentication_verified_from_pinned_ledger':True}
    with (HERE/'ACTUAL_INVENTORY_AUDIT.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
