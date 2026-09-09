"""One private fresh-extraction reproduction in the current interpreter environment."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p,obj):
    with p.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


def compare_metrics(extracted):
    fresh=pd.read_csv(extracted/'reproduced/panel_metrics.csv').set_index(['candidate','panel','baseline'])
    max_cd=max_pp=0.;checks=0
    for stage in ['A','B']:
        old=pd.read_csv(extracted/f'archived_assessment/{stage}_panel_metrics.csv')
        for _,row in old.iterrows():
            for base in ['mean8_CD','xlarge_CD']:
                r=fresh.loc[(row.candidate,row.panel,base)]
                assert r.rows==row.rows
                for x,y in [(r.mae_counts/1e4,row.mae_CD),(r.median_counts/1e4,row.median_absolute_error_CD),
                            (r.p90_counts/1e4,row.p90_absolute_error_CD),(r.baseline_mae_counts/1e4,row[base+'_mae'])]:
                    max_cd=max(max_cd,abs(x-y));np.testing.assert_allclose(x,y,rtol=0,atol=1e-12)
                max_pp=max(max_pp,abs(r.reduction_percent-row[base+'_improvement_percent']))
                np.testing.assert_allclose(r.reduction_percent,row[base+'_improvement_percent'],rtol=0,atol=1e-8)
                assert r.harmed_rows==row[base+'_worse_rows'];checks+=1
    coverage=pd.read_csv(extracted/'reproduced/coverage_metrics.csv').set_index(['panel','family','baseline'])
    cov_checks=0
    for stage in ['A','B']:
        old=pd.read_csv(extracted/f'archived_assessment/{stage}_coverage_metrics.csv')
        for _,row in old.iterrows():
            family=row.family if stage=='A' else ('adaptive' if row.method!='fixed_mean8_scale' else 'upper_free')
            for baseline in ['mean8','xlarge']:
                r=coverage.loc[(row.panel,family,baseline)]
                assert r.eligible_rows==row.eligible_rows and r.eligible_bundles==row.assessed_bundles
                for x,y in [(r.row_coverage,row.eligible_row_coverage),(r.bundle_coverage,row.eligible_bundle_coverage),
                            (r.mean_width_counts/1e4,row.mean_interval_width_CD)]:
                    np.testing.assert_allclose(x,y,rtol=0,atol=1e-12,equal_nan=True)
                assert r.interventions==row[f'project_{baseline}__intervened_rows'];cov_checks+=1
    return {'panel_baseline_comparisons':checks,'coverage_comparisons':cov_checks,
            'max_absolute_CD_metric_drift':max_cd,'max_percentage_point_drift':max_pp}


def main():
    started=time.monotonic();bundle=ROOT/'bundle';archive=ROOT/'private_reproduction.zip'
    assert not archive.exists() and not (ROOT/'verification_start.json').exists(),'Do not duplicate reproduction'
    manifest=json.loads((bundle/'manifest.json').read_text())
    entries=sorted(list(manifest['files'])+['manifest.json'])
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in entries:z.write(bundle/name,arcname='private_reproduction/'+name)
    temporary=Path(tempfile.mkdtemp(prefix='neuralfoil-private-reproduction-',dir='/private/tmp'))
    with zipfile.ZipFile(archive) as z:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(temporary)
    extracted=temporary/'private_reproduction'
    start={'zip_sha256':sha(archive),'manifest_sha256':sha(bundle/'manifest.json'),
           'extracted_manifest_sha256':sha(extracted/'manifest.json'),'temporary_extraction':str(extracted),
           'python':sys.executable,'independently_provisioned_environment':False}
    dump(ROOT/'verification_start.json',start)
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    transcript=ROOT/'fresh_extraction_transcript.txt'
    with transcript.open('x') as log:
        for command in [[sys.executable,'-m','unittest','discover','-v'],[sys.executable,'reproduce.py']]:
            log.write('COMMAND '+repr(command)+'\n');log.flush()
            process=subprocess.Popen(command,cwd=extracted,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in process.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            code=process.wait()
            if code:
                dump(ROOT/'verification_failure.json',{**start,'command':command,'exit_code':code,'transcript_sha256':sha(transcript)})
                raise RuntimeError('Fresh extraction command failed; preserve artifacts')
    report=json.loads((extracted/'reproduced/report.json').read_text())
    checks=compare_metrics(extracted)
    output_hashes={str(p.relative_to(extracted)):sha(p) for p in sorted((extracted/'reproduced').iterdir()) if p.is_file()}
    dump(ROOT/'verification_complete.json',{**start,'status':'PASS','report':report,'metric_snapshot_crosscheck':checks,
        'output_sha256':output_hashes,'transcript_sha256':sha(transcript),'seconds':time.monotonic()-started,
        'package_unchanged':sha(bundle/'manifest.json')==start['manifest_sha256'],
        'scope':'Same installed environment; native feature-level A96+B64 retraining; archived bootstrap/decisions not recomputed'})
    print(json.dumps({'fresh_extraction_verification':'PASS',**checks}),flush=True)


if __name__=='__main__':main()
