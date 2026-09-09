"""Standalone label-free numerical replay and malformed-input checks."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import numpy as np
from predictor import predict, LABELS

HERE=Path(__file__).resolve().parent


def main():
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,expected in manifest['package_hashes'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    artifact=json.loads((HERE/'experimental_policies.json').read_text())
    total=0; maximum=0.
    with np.load(HERE/'inference_references.npz',allow_pickle=False) as refs:
        for name,n in [('historical',8371),('SG_exposed',242),('W_new_challenge',255)]:
            x,b,a,g=[refs[name+'_'+k] for k in ['X62','BASE_CD','all_model_CD','gate']]
            assert len(b)==n
            for label in LABELS:
                actual,strength=predict(artifact,x,b,a,g,label)
                expected=refs[name+'_'+label]
                np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)
                np.testing.assert_array_equal(actual[~g],b[~g])
                assert np.all((strength>=0)&(strength<=1))
                maximum=max(maximum,float(np.max(np.abs(actual-expected))))
            total+=n
            print(name,n,'rows x three policies: PASS')
        x,b,a=x[:2],b[:2],a[:2]; g=np.zeros(2,bool)
        def rejects(model,xx=x,bb=b,aa=a,gg=g):
            try: predict(model,xx,bb,aa,gg)
            except (ValueError,TypeError,KeyError): return
            raise AssertionError('Invalid input/artifact accepted')
        for bad in [np.nan,np.inf,-np.inf,'0.5',-.1,1.1]:
            m=copy.deepcopy(artifact); m['policies']['risk_transfer']['corners'][0]=bad; rejects(m)
        for bad in [np.nan,np.inf,-1]:
            m=copy.deepcopy(artifact); m['policies']['risk_group']['endpoints'][0][0]=bad; rejects(m)
        for bad in [np.nan,np.inf]:
            m=copy.deepcopy(artifact); m['core']['hist']['trees'][0]['value'][0]=bad; rejects(m)
        rejects(artifact,gg=np.zeros(2,int)); rejects(artifact,xx=x[:,:61])
        rejects(artifact,aa=a[:,:7]); rejects(artifact,bb=np.array([0.,.01]))
        bad=x.copy(); bad[0,0]=np.nan; rejects(artifact,xx=bad)
        m=copy.deepcopy(artifact); m['schema']='bad'; rejects(m)
        m=copy.deepcopy(artifact); m['core']['hist']['trees'][0]['left'][0]=999999; rejects(m)
    assert total==8868
    assert 'scipy' not in sys.modules and 'sklearn' not in sys.modules
    print('PASS: 8868 rows, all three policies; maximum CD difference',maximum)
    print('NumPy-only imports, package hashes, exact fallback, malformed-input checks: PASS')


if __name__=='__main__': main()
