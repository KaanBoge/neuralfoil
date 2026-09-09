"""Independent saved-artifact reconciliation: no scientific engine execution."""
from pathlib import Path
import collections,csv,hashlib,io,json,zipfile
from decimal import Decimal
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'model_proposal/kl_bound_study/portable_plan'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(p.read_bytes())
def csvrows(raw):return list(csv.DictReader(io.StringIO(raw.decode())))
def main():
    output=Path(__file__).with_name('QA.json')
    if output.exists():raise FileExistsError(output)
    default=P/'replay_default_attempt_1';isolated=P/'replay_isolated_attempt_1'
    d=load(default/'COMPLETE.json');c=load(isolated/'COMPLETE.json')
    ap=load(P/'ROOT_ISOLATED_REPLAY_APPROVAL.json')
    assert sha((P/'ROOT_ISOLATED_REPLAY_APPROVAL.json').read_bytes())==c['approval_sha256']
    assert sha((default/'COMPLETE.json').read_bytes())==ap['prerequisite_default_complete_sha256']
    assert sha((P/'REGISTRY_v3.json').read_bytes())==ap['source_registry_sha256']
    archives={}
    archive_paths={'addon':P/'kl_harm_private_v1.zip',
      'parent':ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'}
    for origin,path in archive_paths.items():
        raw=path.read_bytes();key='' if origin=='addon' else 'parent_'
        assert sha(raw)==c[key+'archive_sha256']==ap[key+'archive_sha256']
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=z.namelist();prefix=next(n for n in names if n.endswith('manifest.json'))[:-len('manifest.json')]
            files={n[len(prefix):]:z.read(n) for n in names if not n.endswith('/')}
        assert sha(files['manifest.json'])==c[key+'manifest_sha256']==ap[key+'manifest_sha256']
        manifest=json.loads(files['manifest.json'])
        for name,pin in manifest['files'].items():
            assert sha(files[name])==pin['sha256'] and len(files[name])==pin['bytes']
        archives[origin]=files
    for folder,receipt in ((default,d),(isolated,c)):
        for name,pin in receipt['outputs'].items():assert sha((folder/name).read_bytes())==pin
        for name,pin in receipt['executing_source_sha256'].items():
            assert pin==receipt['local_start_source_sha256'][name]==sha(archives['addon']['code/'+name])
            assert sha((P/'fresh_extraction_v1/code'/name).read_bytes())==pin
        assert receipt['end_authentication'] is True
        for event in receipt['materializations']:
            if event.get('origin')=='computed output':
                assert event['file'] in receipt['counts'] and event['operation']=='self serialization and pandas.read_csv; not source input'
                continue
            if 'origin' in event:origin,name=event['origin'],event['file']
            else:origin,name=event['file'].split('/',1)
            assert sha(archives[origin][name])==event['sha256']
    dep=json.loads(archives['addon']['PARENT_REQUIREMENTS.json'])
    labels=('qualified_structural_kl_harm_001','qualified_generic_kl_harm_001')
    expected={(ctx,label) for ctx in dep['contexts'] for label in labels}
    for r in (d,c):
        assert len(r['scalar_checks'])==32 and {(x['context'],x['candidate']) for x in r['scalar_checks']}==expected
        assert all(x['exact'] is True for x in r['scalar_checks'])
        assert len(r['native_checks'])==18 and {x['context'] for x in r['native_checks']}==set(dep['native_contexts'])
        assert all(x['exact'] is True for x in r['native_checks'])
        assert r['certificates']==16
    cert=json.loads(archives['parent']['certificates/STAGE0_CERTIFICATE.json'])
    assert len(cert['records'])==16 and {x['context'] for x in cert['records']}==set(dep['contexts'])
    for ctx,label in expected:
        s=json.loads(archives['addon'][f'scalars/{label}_{ctx}.json'])
        assert s['context']==ctx and s['candidate']==label
    # Raw serialized cell comparisons, independently of pandas parsing.
    changes=[];byte_exact=[];cells=0
    for name,count in c['counts'].items():
        filename=name+'.csv';raw=archives['addon']['expected/'+filename]
        assert (default/filename).read_bytes()==raw
        other=(isolated/filename).read_bytes()
        a,b=csvrows(raw),csvrows(other);assert len(a)==len(b)==count
        assert list(a[0])==list(b[0]);cells+=len(a)*len(a[0])
        if raw==other:byte_exact.append(name)
        for i,(x,y) in enumerate(zip(a,b)):
            for key in x:
                if x[key]!=y[key]:
                    changes.append({'table':name,'row':i,'column':key,'expected_text':x[key],
                      'actual_text':y[key],'decimal_difference':str(Decimal(y[key])-Decimal(x[key])),
                      'binary64_difference':float(y[key])-float(x[key]),
                      'candidate':x.get('candidate'),'assignment':x.get('assignment'),'reference':x.get('reference')})
    assert len(byte_exact)==9 and len(changes)==321 and {x['table'] for x in changes}=={'bootstrap'}
    recorded=load(isolated/'FLOAT_DIFFERENCES.json');assert len(recorded)==c['differences']==316
    rm={(x['row'],x['column']):x for x in recorded};assert len(rm)==316
    am={(x['row'],x['column']):x for x in changes};assert set(rm)<=set(am)
    # Reproduce only CSV parsing (not computations) to check why five serialized
    # cells were equal at the producer's comparison boundary.
    expected_pd=pd.read_csv(io.BytesIO(archives['addon']['expected/bootstrap.csv']))
    actual_pd=pd.read_csv(isolated/'bootstrap.csv')
    for key,r in rm.items():
        actual=float(actual_pd.iloc[key[0]][key[1]])
        assert actual==r['actual'] and float(expected_pd.iloc[key[0]][key[1]])==r['expected']
        assert actual-r['expected']==r['difference']
    extra=[am[k] for k in sorted(set(am)-set(rm))]
    for x in extra:assert float(actual_pd.iloc[x['row']][x['column']])==float(expected_pd.iloc[x['row']][x['column']])
    assert len(extra)==5
    dec=csvrows((isolated/'decisions.csv').read_bytes())
    assert len(dec)==2 and all(r[k]=='False' for r in dec for k in ('performance_advance','robustness_advance'))
    group=collections.Counter(x['column'] for x in changes)
    maxima={k:{'decimal':str(max(abs(Decimal(x['decimal_difference'])) for x in changes if x['column']==k)),
               'binary64':max(abs(x['binary64_difference']) for x in changes if x['column']==k)} for k in group}
    result={'status':'RECONCILED_WITH_SERIALIZATION_QUALIFICATION','csv_cells_compared':cells,'byte_exact_tables':byte_exact,
      'serialized_differences':len(changes),'serialized_counts':dict(group),'maxima':maxima,
      'recorded_differences':316,'recorded_counts':dict(collections.Counter(x['column'] for x in recorded)),
      'serialization_only_extra_cells':extra,'all_changed_cells':changes,
      'scalar_native_certificate_scope':'Authenticated strict executable checks and complete receipts; temporary recalculated scalar/native/certificate values are not separately persisted and were not recomputed in this no-rerun audit.',
      'scalar_checks':32,'native_checks':18,'certificate_checks':16,'materializations':len(c['materializations']),
      'internal_seconds':c['seconds'],'runtime':c['runtime'],'decisions_unchanged':True,
      'complete_sha256':sha((isolated/'COMPLETE.json').read_bytes()),'differences_sha256':sha((isolated/'FLOAT_DIFFERENCES.json').read_bytes())}
    with output.open('x') as f:json.dump(result,f,indent=2)
    print({k:v for k,v in result.items() if k not in ('all_changed_cells','serialization_only_extra_cells')})
if __name__=='__main__':main()
