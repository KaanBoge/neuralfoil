"""Root replay of the older frontier decision, separate from the branch audit."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import assess_policy

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frame, hashes = assess_policy.load_frame()
    expected = pd.read_csv(HERE/'assessment/established_frontier_bootstrap.csv')
    metrics = pd.read_csv(HERE/'assessment/panel_metrics.csv')
    decisions = pd.read_csv(HERE/'assessment/established_frontier_decisions.csv')
    checks = []
    for assignment in [20260906, 20260908]:
        part = frame[frame.split.str.startswith(f'group_{assignment}_')].copy()
        assert len(part) == 8371 and part.nf2_row_id.nunique() == 8371
        err = pd.DataFrame({'group': part.group.to_numpy()})
        for label in ['previous_global','xlarge_CD'] + assess_policy.POLICIES:
            err[label] = abs(part[label].to_numpy()-part.measured_CD.to_numpy())
        grouped = err.groupby('group', sort=True).sum(numeric_only=True)
        assert len(grouped) == 93
        counts = np.random.default_rng(2026090717).multinomial(93, np.full(93, 1/93), size=20000)
        ref = grouped.previous_global.to_numpy()
        for label in assess_policy.POLICIES:
            ce = grouped[label].to_numpy()
            value = float(100*(1-ce.sum()/ref.sum()))
            draws = 100*(1-(counts@ce)/(counts@ref))
            lo, hi = np.quantile(draws,[.025,.975])
            record = expected[(expected.candidate==label)&(expected.assignment==assignment)].iloc[0]
            np.testing.assert_allclose([value,lo,hi],record[['relative_remaining_MAE_reduction_percent',
                'conditional_95pct_lower','conditional_95pct_upper']].to_numpy(float),rtol=0,atol=1e-10)
            checks.append({'candidate':label,'assignment':assignment,'remaining_error_gain_percent':value,
                'lower':float(lo),'upper':float(hi)})
    fields = ['xlarge_CD_improvement_percent','mean8_CD_improvement_percent']
    ref = metrics[(metrics.candidate=='previous_global') & metrics.panel.str.startswith('eligible_only/')][fields].to_numpy()
    assert ref.shape == (8,2)
    positives = []
    for label in assess_policy.POLICIES:
        t = metrics[metrics.candidate==label]
        strict = t[t.panel.str.startswith('strict_source_')][fields].to_numpy()
        ext = t[t.panel.str.startswith('eligible_only/')][fields].to_numpy()
        history = [c['remaining_error_gain_percent'] for c in checks if c['candidate']==label]
        passing = min(history)>=1 and np.all(strict>=0) and np.sum(ext<0)<=np.sum(ref<0) and ext.min()>=ref.min()-1e-6
        wanted = decisions[decisions.candidate==label].iloc[0]
        assert bool(wanted.operational_frontier_advance) == passing
        if passing:
            positives.append(label)
    assert positives == ['unpenalized_transfer']
    for filename, digest in hashes.items():
        assert sha(filename) == digest
    result = {'status':'passed', 'independent_older_frontier_bootstrap_records':checks,
        'older_frontier_advances':positives,'primary_rule_is_separate':True,
        'max_bootstrap_comparison_tolerance':1e-10,'source_sha256':sha(Path(__file__)),
        'assessment_sha256':sha(HERE/'assessment/report.json'),
        'independent_branch_audit_sha256':sha(HERE/'review/audit_results.json'),
        'portable_manifest_sha256':sha(HERE/'portable/manifest.json'),
        'uncertainty_note':'One older-frontier gain interval includes zero; these are descriptive adaptive comparisons, not confirmed independent gains.'}
    (HERE/'DELIVERY_QA.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
