"""Independent equation replay adapted from prior independent audit, not assessor."""
import ast,json,hashlib,zipfile,io,time,traceback,sys
from pathlib import Path
import pandas as pd
import numpy as np
from audit_kl_calibration import HERE,P,checked,sha
PIN='47c5a91da283e9e59ad51821e6661a54275946917c965a56d63c034d688bb01d'
def main():
    start=time.monotonic();rec=json.loads(checked(P/'assess/COMPLETE.json',PIN))
    for n,s in rec['outputs'].items():checked(P/'assess'/n,s)
    score=json.loads(checked(P/'score/COMPLETE.json',rec['predecessor_sha256']));assert score['finished_UTC']<rec['started_UTC']
    for n,s in score['outputs'].items():checked(P/'score'/n,s)
    freeze=json.loads(checked(P/'IMPLEMENTATION_FREEZE_v2.json',rec['implementation_sha256']))
    for n,s in freeze['source_sha256'].items():checked(P/n,s)
    for n,s in freeze['external_source_sha256'].items():checked(n,s)
    app=json.loads(checked(P/'ROOT_ASSESSMENT_APPROVAL.json',rec['approval_sha256']));assert app['authorized_phases']==['assess']
    arc=P.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip';a=zipfile.ZipFile(io.BytesIO(checked(arc,rec['archive_sha256'])))
    mn=next(n for n in a.namelist() if n.endswith('manifest.json'));prefix=mn[:-13];raw=a.read(mn);assert sha(raw)==rec['manifest_sha256'];manifest=json.loads(raw)['files']
    def member(n):
        raw=a.read(prefix+n);assert sha(raw)==manifest[n]['sha256'];return raw
    schema=json.loads(member('scoring/schema.json'));panels=json.loads(member('scoring/panels.json'))
    with np.load(io.BytesIO(member('scoring/frame.npz')),allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
    cols={}
    for row in schema['columns']:
        v=arrays[row['key']]
        if row['dtype']=='object':
            v=np.array([None if t==0 else str(s) if t==1 else s=='1' if t==2 else int(s) if t==3 else float.fromhex(s) if t==4 else (_ for _ in ()).throw(ValueError('tag')) for s,t in zip(v,arrays[row['key']+'_kind'])],object)
        cols[row['name']]=v
    original=pd.DataFrame(cols);frame=original.copy(deep=True);labels=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
    for split in frame.split.unique():
        n=f'predictions_{split}.csv';f=pd.read_csv(io.BytesIO(checked(P/'score'/n,score['outputs'][n])),low_memory=False);mask=frame.split.eq(split)
        if split not in ['SG_exposed','W_new_challenge']:
            assert f.nf2_row_id.is_unique;f=f.set_index('nf2_row_id').loc[frame.loc[mask,'nf2_row_id']]
        else:np.testing.assert_array_equal(f['indices'],np.arange(mask.sum()))
        for label in labels:
            for suffix in ['','__effective_fraction','__strength','__intervened']:frame.loc[mask,label+suffix]=f[label+suffix].to_numpy()
    pd.testing.assert_frame_equal(frame[original.columns],original,check_exact=True)
    tables={n[:-4]:pd.read_csv(io.BytesIO(checked(P/'assess'/n,s)),low_memory=False) for n,s in rec['outputs'].items() if n.endswith('.csv')}
    # Re-serialization must reproduce every cell/column of the stored all-row CSV.
    buf=io.StringIO();frame.to_csv(buf,index=False);rebuilt=pd.read_csv(io.StringIO(buf.getvalue()),low_memory=False)
    pd.testing.assert_frame_equal(rebuilt,tables['all_row_predictions'],check_exact=True)
    tables['all_row_predictions']=frame
    for e in rec['archive_materializations']:assert e['sha256']==manifest[e['file']]['sha256']
    assert {e['file'] for e in rec['archive_materializations']}=={'inventory.json','scoring/frame.npz','scoring/schema.json','scoring/panels.json'}
    assert {e['member'] for e in rec['archive_materializations'] if e['operation']=='NPZ member'}==set(arrays)
    reads=rec['phase_file_reads'];assert len(reads)==17
    for e in reads:
        path=Path(e['path']);assert path.parent==P/'score';raw=checked(path,e['sha256']);assert e['sha256']==score['outputs'][path.name] and len(raw)==e['bytes']
    # Reuse our existing independent equations; only loader and fixed table sizes change.
    src=(HERE/'stage1_v2_audit/audit_metrics.py').read_text();tree=ast.parse(src)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    # first two statements load the old report/tables; inject authenticated new tables.
    node.body=node.body[2:]
    body=ast.unparse(node).replace("labels = report['candidates'] + report['controls']","labels = list(table_labels)")
    for old,new in [('len(labels) == 15','len(labels) == 17'),('len(table) == 465','len(table) == 527'),('len(groups) == 2790','len(groups) == 3162'),('len(boot) == 150','len(boot) == 238'),('len(harm) == 3255','len(harm) == 4743'),('len(risk) == 465','len(risk) == 527')]:body=body.replace(old,new)
    # Replace final legacy summary, preserving all preceding numerical checks.
    parsed=ast.parse(body);parsed.body[0].body[-1]=ast.parse("return {'checks': COUNT, 'warnings': WARNINGS, 'decisions': decisions}").body[0]
    support='\n'.join(ast.unparse(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='eq')
    ns={'np':np,'pd':pd,'frames':tables,'table_labels':list(tables['panel_metrics'].candidate.unique()),'COUNT':0,'WARNINGS':[]}
    exec(support,ns);exec(compile(ast.fix_missing_locations(parsed),'<independent adapted audit>','exec'),ns);result=ns['main']()
    assert all(not r['advance'] for r in result['decisions'])
    result.update(status='PASS',seconds=time.monotonic()-start,complete_sha256=PIN,panels=31,panel_rows=527,bootstrap_rows=238,typed_original_columns=len(original.columns),typed_original_rows=len(original),archive_events=len(rec['archive_materializations']),score_CSV_reads=17,table_counts={n:len(f) for n,f in tables.items()},scope='independent equations on authenticated reconstructed typed frame; no fits or new candidates')
    return result
if __name__=='__main__':
    out=HERE/'KL_ASSESSMENT_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        name=HERE/'KL_ASSESSMENT_AUDIT_FAILURE.txt';i=1
        while name.exists():i+=1;name=HERE/f'KL_ASSESSMENT_AUDIT_FAILURE_{i}.txt'
        with name.open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
