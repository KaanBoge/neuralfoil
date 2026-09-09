"""Source metadata and synthetic reader tests only. Does not export study data."""
from pathlib import Path
import hashlib,io,json,sys,tempfile
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
P=HERE.parents[1]/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan'
sys.path.insert(0,str(P))
import export_support as e
PIN='dc17af0ed1a5211e21d2dc0dc0f015624a4366c4b051584e509ff3f8e1e229e0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert sha(P/'REGISTRY_v3.json')==PIN
    r=json.loads((P/'REGISTRY_v3.json').read_bytes())
    for name,h in r['implementation_sha256'].items():assert sha(P/name)==h
    for name,h in r['preserved_drafting_snapshot_sha256'].items():assert sha(P/'drafting_snapshot_v2'/name)==h
    original=(np.load,pd.read_csv);checks=[]
    # Original path changes AFTER authentication: reader must still consume pinned bytes.
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'a.csv';raw=b'x\n1\n';path.write_bytes(raw)
        with e.ReaderTrace({str(path):hashlib.sha256(raw).hexdigest()}) as tr:
            parser=tr.original_pd
            def mutate_then_parse(buffer,*args,**kw):
                path.write_bytes(b'x\n999\n');return parser(buffer,*args,**kw)
            tr.original_pd=mutate_then_parse
            assert pd.read_csv(path).x.tolist()==[1]
            tr.original_pd=parser
        checks.append('authenticated path bytes survive post-read path mutation')
    assert (np.load,pd.read_csv)==original
    raw=b'x\n1\n'
    for kind in ['offset','unknown_bytes']:
        with e.ReaderTrace({'synthetic.csv':hashlib.sha256(raw).hexdigest()}):
            source=io.BytesIO(raw if kind=='offset' else b'x\n2\n')
            if kind=='offset':source.seek(1)
            try:pd.read_csv(source)
            except ValueError:pass
            else:raise AssertionError('unregistered source accepted')
        checks.append(kind+' refused and wrappers restored');assert (np.load,pd.read_csv)==original
    stream=io.BytesIO();np.savez(stream,used=np.array([1.]),unused=np.array([2.]));raw=stream.getvalue()
    with e.ReaderTrace({'synthetic.npz':hashlib.sha256(raw).hexdigest()}) as tr:
        with np.load(io.BytesIO(raw),allow_pickle=False) as z:
            assert z.files==['used','unused'];assert tr.events[0]['members']==[]
            assert z['used'][0]==1.
        assert [v['name'] for v in tr.events[0]['members']]==['used']
    checks.append('member enumeration distinct from actual member materialization')
    assert (np.load,pd.read_csv)==original
    return {'status':'PASS_SOURCE_AND_SYNTHETIC_ONLY','registry_sha256':PIN,'implementation_files_verified':len(r['implementation_sha256']),'preserved_source_files_verified':len(r['preserved_drafting_snapshot_sha256']),'input_registry_entries_metadata_only':len(r['inputs']),'test_sha256':sha(__file__),'checks':checks,'real_export':False,'empirical_arrays_opened':False}
if __name__=='__main__':
    out=HERE/'PORTABLE_EXPORT_V3_QA.json';assert not out.exists()
    result=main()
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
