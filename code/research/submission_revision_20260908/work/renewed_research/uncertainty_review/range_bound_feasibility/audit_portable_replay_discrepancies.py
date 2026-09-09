"""Authenticate completed package/replays and independently enumerate saved cells."""
from pathlib import Path
from collections import Counter
import hashlib,io,json,zipfile,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
P=HERE.parents[1]/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan'
ZIP='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
MAN='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,h=None):
    if h:assert sha(p)==h
    return json.loads(Path(p).read_bytes())
def main():
    archive=P/'qualified_harm_private_v1.zip';assert sha(archive)==ZIP
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();assert len(names)==141 and len(set(names))==141
        mraw=z.read('manifest.json');assert hashlib.sha256(mraw).hexdigest()==MAN;manifest=json.loads(mraw)
        assert set(manifest['files'])==set(names)-{'manifest.json'} and manifest['human_release_approval'] is False
        for name,pin in manifest['files'].items():
            raw=z.read(name);assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
            assert sha(P/'fresh_extraction_v1'/name)==pin['sha256']
        assert sha(P/'fresh_extraction_v1/manifest.json')==MAN
    default=load(P/'replay_default_v1/REPORT.json','88cb579de733f07282d9dcecc7df3b853354908132bebbd1aa922511d8d322f2')
    optional=load(P/'replay_features_v1/REPORT.json','8f8de777bed71f8181c275370ed82abf7a2d3e6f8640654908be463135b67eb4')
    differences=load(P/'replay_features_v1/FLOAT_DIFFERENCES.json','fa3c948d81972dd74ac22f6762ca9ec1d39512dd2225f04db5c026364b11f51f')
    assert load(P/'replay_default_v1/FLOAT_DIFFERENCES.json')==[]
    assert default['status']=='EXACT_REPLAY_PASS' and optional['status']=='COMPLETE_WITH_EXPLICIT_FLOAT_DIFFERENCES'
    for report in [default,optional]:
        assert len(report['scalar_checks'])==32 and all(x['exact'] for x in report['scalar_checks'])
        assert len({(x['context'],x['candidate']) for x in report['scalar_checks']})==32
        assert len(report['native_checks'])==18 and all(x['both_procedures_exact'] for x in report['native_checks'])
        assert sum(x['rows'] for x in report['native_checks'])==38227 and report['tree_certificates']==16
        assert report['all_decisions_unchanged'] is True
    assert len(optional['optional_feature_checks'])==34 and len({(x['role'],x['context']) for x in optional['optional_feature_checks']})==34 and all(x['exact'] for x in optional['optional_feature_checks'])
    assert not default['optional_feature_checks']
    actual=[];byte_equal={'default':0,'optional':0};tables=[]
    expected_dir=P/'fresh_extraction_v1/expected'
    for p in sorted(expected_dir.glob('*.csv')):
        name=p.stem;tables.append(name);expected=pd.read_csv(p,low_memory=False)
        for run,dirname in [('default','replay_default_v1'),('optional','replay_features_v1')]:
            path=P/dirname/p.name;frame=pd.read_csv(path,low_memory=False)
            assert list(frame.columns)==list(expected.columns) and len(frame)==len(expected)
            byte_equal[run]+=sha(path)==sha(p)
            for col in frame:
                x,y=frame[col],expected[col]
                if pd.api.types.is_numeric_dtype(x) and x.dtype!=bool:
                    np.testing.assert_array_equal(pd.isna(x),pd.isna(y));ix=np.flatnonzero((x.to_numpy()!=y.to_numpy())&~pd.isna(x.to_numpy()))
                    if run=='default':assert not len(ix),(name,col)
                    for i in ix:
                        assert run=='optional'
                        actual.append({'table':name,'column':col,'row':int(i),'actual':float(x.iloc[i]),'expected':float(y.iloc[i]),'difference':float(x.iloc[i]-y.iloc[i])})
                else:pd.testing.assert_series_equal(x,y,check_names=False)
    assert len(tables)==11
    key=lambda r:(r['table'],r['column'],r['row'])
    assert sorted(actual,key=key)==sorted(differences,key=key)
    assert len(actual)==186 and {r['table'] for r in actual}=={'bootstrap'}
    counts=Counter(r['column'] for r in actual);assert counts=={'conditional_95pct_lower':98,'conditional_95pct_upper':86,'bootstrap_fraction_benefit_positive':2}
    boot=pd.read_csv(expected_dir/'bootstrap.csv');ci=[r for r in actual if r['column'].startswith('conditional_')]
    signs=[]
    for r in actual:
        r.update({k:boot.iloc[r['row']][k].item() if isinstance(boot.iloc[r['row']][k],np.generic) else boot.iloc[r['row']][k] for k in ['candidate','assignment','reference']})
        if r['column']=='bootstrap_fraction_benefit_positive':
            assert r['candidate']=='calibrated_incremental_harm_001' and r['reference']=='qualified_generic_harm_001';signs.append(r)
    assert {r['assignment'] for r in signs}=={20260906,20260908}
    maximum=max(ci,key=lambda r:abs(r['difference']))
    # The already audited exact affected sign rows are corroborative, not an imposed tolerance.
    prior=load(HERE/'stage1_v2_audit/METRIC_QA.json','22125eb867ab2f33157932d1e9e5091c8fc17c5532e9a3b67f064429e493a20c')
    for r in signs:
        old=next(x for x in prior['zero_diagnostic_warnings'] if x['assignment']==r['assignment'])
        assert r['actual']==old['CSV_replay_fraction'] and r['expected']==old['saved_fraction']
        r['previous_independent_max_abs_draw_benefit_pp']=old['maximum_absolute_draw_benefit_pp']
    return {'status':'AUDITED_EXACT_DEFAULT_AND_QUALIFIED_ISOLATED_DIFFERENCES','archive_sha256':ZIP,'manifest_sha256':MAN,'source_sha256':sha(__file__),'extracted_payloads_verified':140,'csv_tables_compared':11,'byte_identical_csv_tables':byte_equal,'difference_cells':186,'difference_counts':dict(counts),'CI_max_abs_difference_pp':abs(maximum['difference']),'CI_maximum_record':maximum,'CI_mean_abs_difference_pp':float(np.mean([abs(x['difference']) for x in ci])),'strict_zero_sign_records':signs,'all_difference_records':actual,'scalar_checks_each':32,'native_cases_each':18,'tree_certificates_each':16,'optional_feature_cases':34,'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},'scope':'No replay/refitting performed here. Authenticated saved receipts and every saved table difference reconciled. Isolated output is not generalized numeric PASS.'}
if __name__=='__main__':
    out=HERE/'PORTABLE_REPLAY_DISCREPANCY_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        import traceback
        with (HERE/'PORTABLE_REPLAY_DISCREPANCY_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k!='all_difference_records'},indent=2))
