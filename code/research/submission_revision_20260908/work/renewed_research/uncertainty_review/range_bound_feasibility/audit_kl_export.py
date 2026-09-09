"""Metadata/byte/source-only audit. Never parses scalar/CSV/NPZ payloads."""
from pathlib import Path
import json,hashlib,zipfile,io,ast,collections,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=ROOT/'model_proposal/kl_bound_study/portable_plan';S=P.parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(p,h=None):
    raw=Path(p).read_bytes()
    if h:assert sha(raw)==h,str(p)
    return raw
def archive(p,ah,mh):
    z=zipfile.ZipFile(io.BytesIO(read(p,ah)));names=z.namelist();assert len(names)==len(set(names));files={n:z.read(n) for n in names};raw=files.pop('manifest.json');assert sha(raw)==mh;man=json.loads(raw)
    assert set(man['files'])==set(files)
    for n,b in files.items():assert man['files'][n]=={'sha256':sha(b),'bytes':len(b)}
    return files,man,len(raw)
def main():
    start=time.monotonic();reg=json.loads(read(P/'REGISTRY_v3.json','227aa87d058747052b09e5c907691e0c846697dfe2c61e85437f4e161f7095fd'))
    for n,h in reg['sources'].items():read(P/n,h)
    for n,h in reg['inputs'].items():read(n,h)
    attempt=json.loads(read(P/'kl_harm_private_v1.zip.attempt.json'));approval=json.loads(read(P/'ROOT_EXPORT_APPROVAL.json',attempt['approval_sha256']));assert approval['authorized_phases']==['export']
    receipt=json.loads(read(P/'kl_harm_private_v1.zip.receipt.json','beae8c2a6def2c1508cf2d1022e67135d0507979ab50e37debfae55057cf2316'))
    data,man,mlen=archive(P/'kl_harm_private_v1.zip','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')
    parent,pm,_=archive(S.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154')
    assert len(data)==receipt['payload_files']==102;assert sum(map(len,data.values()))+mlen==receipt['uncompressed_bytes']==53369819
    dep=json.loads(data['PARENT_REQUIREMENTS.json']);assert dep['required_members']=={n:sha(b) for n,b in parent.items()}
    w=json.loads(data['SOURCE_WITNESS.json']);assert sha(data['SOURCE_WITNESS.json'])=='c0bd8ff942dd760484797ac97b66942ddc0c15a3063da975fee95f97a7300236'
    assert w['inputs']==reg['inputs'];ledger=w['materializations'];assert len(ledger)==343
    js=[e for e in ledger if e.get('operation')=='JSON parse'];assert len(js)==1 and js[0]['file']=='inventory.json' and js[0]['sha256']==sha(parent['inventory.json'])
    native=[e for e in ledger if 'member' in e];assert len(native)==342
    for e in native:
        prefix,ctx=e['file'].rsplit('/',1)
        if prefix=='KL native':raw=read(S/'score'/f'inference_{ctx}.npz')
        else:assert prefix=='parent native';raw=parent[f'native/{ctx}.npz']
        assert sha(raw)==e['sha256']
    counts=collections.Counter(n.split('/')[0] for n in data if '/' in n);assert counts=={'scalars':32,'predictions':18,'prediction_csv':17,'expected':10,'evidence':15,'code':7}
    for n,b in data.items():
        if n.startswith('scalars/'):assert b==read(S/'calibrate'/('calibrator_'+n.split('/')[1]))
        elif n.startswith('prediction_csv/'):assert b==read(S/'score'/('predictions_'+n.split('/')[1]))
        elif n.startswith('expected/'):assert b==read(S/'assess'/n.split('/')[1])
        elif n.startswith('evidence/'):assert b==read(reg['evidence'][n.split('/',1)[1]])
    def asts(raw):return {n.name:n for n in ast.parse(raw.decode()).body if isinstance(n,ast.FunctionDef)}
    for target,source,key in [('code/adapter.py',ROOT/'kl_confidence_production/confidence.py','adapter_AST'),('code/overlay.py',S/'run_experiment.py','overlay_AST')]:
        original=asts(read(source));copied=asts(data[target])
        for name,pin in w[key].items():
            dump=ast.dump(original[name],include_attributes=False);assert ast.dump(copied[name],include_attributes=False)==dump
            # Stored ast.dump witnesses are interpreter-version representations.
            assert sha(dump.encode())==pin
    for n in ['shared.py','integrity.py','replay.py','test_portable.py']:assert data['code/'+n]==read(P/n)
    return {'status':'PASS_METADATA_SOURCE_ONLY','payload_files':102,'archive_bytes':len(read(P/'kl_harm_private_v1.zip')),'export_events':343,'JSON_parses':1,'NPZ_member_events':342,'inventory':dict(counts),'seconds':time.monotonic()-start,'scope':'authenticated rawbytes/metadata/sourceAST only; no scientific scalar/CSV/NPZ parsing, no extraction/replay','export_duration':'not internally measured'}
if __name__=='__main__':
    r=main()
    with (HERE/'KL_EXPORT_QA.json').open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
