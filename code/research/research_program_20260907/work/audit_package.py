"""Read-only independent private-package delivery audit; never fits or extracts."""
from pathlib import Path
import hashlib,json,zipfile
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
P=PROJECT/'reproduction_20260908_private'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
    v=read(P/'verification_complete.json');e=Path(v['temporary_extraction']);m=read(P/'bundle/manifest.json')
    assert sha(P/'private_reproduction.zip')==v['zip_sha256']
    assert sha(P/'bundle/manifest.json')==sha(e/'manifest.json')==v['manifest_sha256']==v['extracted_manifest_sha256']
    with zipfile.ZipFile(P/'private_reproduction.zip') as z:
        assert set(z.namelist())=={'private_reproduction/'+n for n in list(m['files'])+['manifest.json']}
        for n,h in m['files'].items():
            assert sha(e/n)==sha(P/'bundle'/n)==h
            assert hashlib.sha256(z.read('private_reproduction/'+n)).hexdigest()==h
    for n,h in v['output_sha256'].items():assert sha(e/n)==h
    t=(P/'fresh_extraction_transcript.txt').read_text();assert sha(P/'fresh_extraction_transcript.txt')==v['transcript_sha256']
    assert t.count('COMMAND ')==2 and 'Ran 33 tests' in t and '\nOK\n' in t
    assert len([l for l in t.splitlines() if l.startswith('test_') and l.endswith(' ... ok')])==33
    records=[json.loads(l) for l in t.splitlines() if l.startswith('{')]
    assert len(records)==17
    for i,r in enumerate(records[:-1],1):
        assert r['A_core_fits']==6*i and r['B_inner_core_fits']==3*i and r['B_scale_fits']==i
        assert r['A_calibrators']==3*i and r['B_calibrators']==i
    report=read(e/'reproduced/report.json');assert report==v['report']==records[-1]
    assert report['status']=='PASS' and report['native_array_parity']==report['calibrator_parity']=='exact'
    assert report['A_core_fits']+report['B_inner_core_fits']+report['B_scale_fits']==160
    assert report['A_calibrators']+report['B_calibrators']==64
    native_fields=0;native_values=0
    for ref in (e/'references').glob('*_inference_*.npz'):
        context=ref.stem.split('_inference_',1)[1]
        with np.load(ref) as old,np.load(e/f'reproduced/predictions_{context}.npz') as new:
            for k in old.files:
                np.testing.assert_array_equal(old[k],new[k]);native_fields+=1;native_values+=old[k].size
    fresh=pd.read_csv(e/'reproduced/panel_metrics.csv').set_index(['candidate','panel','baseline'])
    coverage=pd.read_csv(e/'reproduced/coverage_metrics.csv').set_index(['panel','family','baseline'])
    nc=nv=0;maxcd=maxpp=0.
    for stage in ['A','B']:
        old=pd.read_csv(e/f'archived_assessment/{stage}_panel_metrics.csv')
        for _,r in old.iterrows():
            for base in ['mean8_CD','xlarge_CD']:
                f=fresh.loc[r.candidate,r.panel,base];assert f.rows==r.rows and f.harmed_rows==r[base+'_worse_rows']
                for x,y in [(f.mae_counts/1e4,r.mae_CD),(f.median_counts/1e4,r.median_absolute_error_CD),(f.p90_counts/1e4,r.p90_absolute_error_CD),(f.baseline_mae_counts/1e4,r[base+'_mae'])]:
                    maxcd=max(maxcd,abs(x-y));assert abs(x-y)<=1e-12
                delta=abs(f.reduction_percent-r[base+'_improvement_percent']);maxpp=max(maxpp,delta);assert delta<=1e-8;nc+=1
        old=pd.read_csv(e/f'archived_assessment/{stage}_coverage_metrics.csv')
        for _,r in old.iterrows():
            family=r.family if stage=='A' else ('adaptive' if r.method=='adaptive_scale' else 'upper_free')
            for base in ['mean8','xlarge']:
                f=coverage.loc[r.panel,family,base]
                assert f.eligible_rows==r.eligible_rows and f.eligible_bundles==r.assessed_bundles and f.interventions==r['project_'+base+'__intervened_rows']
                np.testing.assert_allclose([f.row_coverage,f.bundle_coverage,f.mean_width_counts/1e4],[r.eligible_row_coverage,r.eligible_bundle_coverage,r.mean_interval_width_CD],atol=1e-12,rtol=0)
                nv+=1
    assert nc==1736 and nv==310
    assert maxcd==v['metric_snapshot_crosscheck']['max_absolute_CD_metric_drift'] and maxpp==v['metric_snapshot_crosscheck']['max_percentage_point_drift']
    result=dict(status='PASS',bundle_files=len(m['files']),outputs=len(v['output_sha256']),tests=33,fits=160,calibrators=64,native_reference_fields=native_fields,native_values=native_values,panel_baseline_comparisons=nc,coverage_comparisons=nv,max_CD_drift=maxcd,max_pp_drift=maxpp,verification_sha256=sha(P/'verification_complete.json'),audit_sha256=sha(Path(__file__)))
    (HERE/'PACKAGE_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()
