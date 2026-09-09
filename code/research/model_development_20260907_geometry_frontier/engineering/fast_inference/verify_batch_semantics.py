"""Supplemental parity test: distinguish inherited batch rounding from adapter change."""
from pathlib import Path
import hashlib,importlib.util,json
import numpy as np
from prepared import authenticated_artifact,prepare,LABELS
HERE=Path(__file__).resolve().parent;ORIGINAL=HERE.parents[2]/'model_development_20260907_risk_policy/portable'
def main():
    artifact,_=authenticated_artifact(ORIGINAL);fast=prepare(artifact)
    spec=importlib.util.spec_from_file_location('original',ORIGINAL/'predictor.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    chunks=0;maximum=0.;maximum_strength=0.
    with np.load(ORIGINAL/'inference_references.npz',allow_pickle=False) as refs:
        for name in ['historical','SG_exposed','W_new_challenge']:
            a=tuple(refs[name+'_'+k] for k in ['X62','BASE_CD','all_model_CD','gate'])
            for label in LABELS:
                full=old.predict(artifact,*a,label)
                for start in range(0,len(a[1]),32):
                    small=tuple(v[start:start+32] for v in a);p=fast.predict(*small,label);q=old.predict(artifact,*small,label)
                    for got,expected in zip(p,q):np.testing.assert_array_equal(got,expected)
                    maximum=max(maximum,float(abs(q[0]-full[0][start:start+32]).max()));maximum_strength=max(maximum_strength,float(abs(q[1]-full[1][start:start+32]).max()));chunks+=1
                for row in [0,len(a[1])-1]:
                    small=tuple(v[row:row+1] for v in a)
                    for p,q in zip(fast.predict(*small,label),old.predict(artifact,*small,label)):np.testing.assert_array_equal(p,q)
                # Inputs are not cached by identity: intentional caller changes
                # are revalidated and receive corresponding changed predictions.
                changed=[v[:3].copy() for v in a];changed[0][0,0]+=.01
                for p,q in zip(fast.predict(*changed,label),old.predict(artifact,*changed,label)):np.testing.assert_array_equal(p,q)
    result={'status':'PASS every32rowchunk original/prepared CD and strength bit-identical','chunks':chunks,'singleton_and_changed_input_parity':True,'original_inherited_batch_CD_roundoff':maximum,'original_inherited_batch_strength_roundoff':maximum_strength,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'batch_semantics.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
