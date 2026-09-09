"""Loader race simulation only; no timing, fitting or original-file mutations."""
from pathlib import Path
from unittest.mock import patch
import hashlib,json
import numpy as np
from prepared import authenticated_artifact,prepare,MANIFEST_SHA256
from checked_loader import load_prepared_checked
HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parents[2]/'model_development_20260907_risk_policy/portable'

def main():
    artifact,manifest=authenticated_artifact(ORIGINAL);reference=prepare(artifact)
    model_path=ORIGINAL/'experimental_policies.json'
    read=Path.read_bytes;counts={};changed=False
    malicious=json.dumps({'schema':'malicious'}).encode()
    def simulated_change(path):
        nonlocal changed
        key=str(path);counts[key]=counts.get(key,0)+1
        if path==model_path:
            if changed:return malicious
            result=read(path);changed=True
            return result
        return read(path)
    with patch.object(Path,'read_bytes',simulated_change):
        loaded=load_prepared_checked(ORIGINAL)
    assert changed and counts[str(model_path)]==1
    assert counts[str(ORIGINAL/'manifest.json')]==1
    for name in manifest['package_hashes']:assert counts[str(ORIGINAL/name)]==1
    with np.load(ORIGINAL/'inference_references.npz',allow_pickle=False) as refs:
        args=tuple(refs['historical_'+k][:32] for k in ['X62','BASE_CD','all_model_CD','gate'])
        for label in ['risk_transfer','unpenalized_transfer','risk_group']:
            for got,expected in zip(loaded.predict(*args,label),reference.predict(*args,label)):
                np.testing.assert_array_equal(got,expected)
    def tampered_read(path):return malicious if path==model_path else read(path)
    with patch.object(Path,'read_bytes',tampered_read):
        try:load_prepared_checked(ORIGINAL)
        except ValueError as error:assert 'Package hash mismatch' in str(error)
        else:raise AssertionError('Changed model bytes accepted')
    try:load_prepared_checked(ORIGINAL,'0'*64)
    except ValueError as error:assert 'Manifest authentication failed' in str(error)
    else:raise AssertionError('Bad manifest accepted')
    # A malicious member name is rejected even if a caller explicitly trusts
    # that synthetic manifest's digest. No filesystem access to that path occurs.
    bad_manifest=json.dumps({'package_hashes':{'../outside.json':'0'*64}}).encode()
    with patch.object(Path,'read_bytes',lambda path:bad_manifest if path.name=='manifest.json' else (_ for _ in ()).throw(AssertionError('Invalid member read'))):
        try:load_prepared_checked(ORIGINAL,hashlib.sha256(bad_manifest).hexdigest())
        except ValueError as error:assert 'Invalid manifest member path' in str(error)
        else:raise AssertionError('Unsafe member path accepted')
    # Confirm frozen original package manifest and files remain intact.
    authenticated_artifact(ORIGINAL)
    result={'status':'PASS checked-loader one-read authentication tests','model_read_count':counts[str(model_path)],'each_package_member_read_once':True,
            'change_after_read_uses_authenticated_original':True,'changed_returned_bytes_rejected':True,'invalid_manifest_and_member_path_rejected':True,
            'all_three_policy_CD_strength_parity':True,'setup_benchmarked':False,'upstream_manifest_sha256':MANIFEST_SHA256,
            'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'checked_loader_tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
