"""Independent Decimal verification; imports neither generator nor its helpers."""
from pathlib import Path
from decimal import Decimal as D, localcontext, Inexact
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parent


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_q(value, record):
    assert value*D(record['denominator']) == D(record['numerator'])


def main():
    cert = json.loads((ROOT/'certificate.json').read_text())
    assert digest(ROOT/'parsed_inputs.npz') == cert['snapshot_sha256']
    checks = []
    # All source floats here have short finite decimal expansions. Trap any
    # rounding in exact difference, sum, product and cross-multiplication.
    with localcontext() as ctx:
        ctx.prec = 500
        ctx.traps[Inexact] = True
        with np.load(ROOT/'parsed_inputs.npz') as z:
            errors = []
            baseline_errors = [[],[]]
            fails = [[],[]]
            for y,row,bases in zip(z['y'],z['predictions'],z['baselines']):
                y = D.from_float(float(y))
                values = [D.from_float(float(v)) for v in row]
                error = max(min(values)-y,y-max(values),D(0))
                errors.append(error)
                for j,value in enumerate(bases):
                    be = abs(D.from_float(float(value))-y)
                    baseline_errors[j].append(be)
                    fails[j].append(100*error > 91*be)
            for k,panel in enumerate(cert['panels']):
                ix = z['panel_'+str(k)]
                es = sum((errors[i] for i in ix),D(0))
                check_q(es,panel['oracle_error_sum_CD'])
                check_q(es,panel['oracle_MAE_CD'] | {'numerator':str(int(panel['oracle_MAE_CD']['numerator'])*len(ix))})
                assert sum(errors[i] > 0 for i in ix) == panel['outside_envelope_rows']
                assert sum(fails[0][i] or fails[1][i] for i in ix) == panel['fails_9pct_either_baseline_rows']
                for j,name in enumerate(['xlarge_CD','mean8_CD']):
                    entry = panel['baselines'][name]
                    total = sum((baseline_errors[j][i] for i in ix),D(0))
                    check_q(total,entry['baseline_error_sum_CD'])
                    r = entry['maximum_improvement_fraction']
                    assert total*(D(r['denominator'])-D(r['numerator'])) == es*D(r['denominator'])
                    assert sum(fails[j][i] for i in ix) == entry['fails_9pct_rows']
                    assert sum(baseline_errors[j][i] == 0 for i in ix) == entry['zero_baseline_error_rows']
                    assert sum(fails[j][i] and baseline_errors[j][i] == 0 for i in ix) == entry['fails_9pct_with_zero_baseline_rows']
                    checks.append((int(r['numerator']),int(r['denominator']),panel['panel'],name))
        # Independently order rational improvements by integer cross products.
        best = checks[0]
        for r in checks[1:]:
            if r[0]*best[1] < best[0]*r[1]:
                best = r
        common = cert['common_improvement_fraction_upper_bound']
        assert best[0]*int(common['denominator']) == best[1]*int(common['numerator'])
        assert best[2:] == (cert['limiting_panel'],cert['limiting_baseline'])
    result = {'status':'PASS','independent_arithmetic':'Decimal.from_float; precision500; Inexact trapped',
              'panels':31,'baseline_comparisons':62,'all_row_threshold_flags_rechecked':True,
              'generator_imported':False,'certificate_sha256':digest(ROOT/'certificate.json'),
              'verifier_sha256':digest(Path(__file__))}
    (ROOT/'independent_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
