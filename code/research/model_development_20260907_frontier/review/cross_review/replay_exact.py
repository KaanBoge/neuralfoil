"""Independent witness verification only: no optimizer or witness construction."""
from pathlib import Path
from fractions import Fraction as Q
import hashlib, json, sys, time

HERE = Path(__file__).resolve().parent
FRONT = HERE.parents[1]
FEAS = FRONT.parent / 'model_development_20260907_positive/feasibility'
sys.path.insert(0, str(FEAS))
import solve_feasibility as original

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unpack(v): return Q(int(v['numerator']), int(v['denominator']))
def pack(v): return {'numerator': str(v.numerator), 'denominator': str(v.denominator)}

def main():
    started = time.monotonic()
    path = FRONT/'fixed_class_limit/exact_report.json'
    stored = json.loads(path.read_text())
    d, cols, hashes = original.load_inputs()
    assert hashes == stored['input_sha256']
    panels = original.panels(d)
    assert len(cols)==21 and len(panels)==23 and len(d)==29856
    # Convert each original pandas-parsed binary float BEFORE any arithmetic.
    y = [Q(float(v)) for v in d.measured_CD]
    p = [[Q(float(v)) for v in row] for row in d[cols].to_numpy()]
    bs = {b:[Q(float(v)) for v in d[b]] for b in ['xlarge_CD','mean8_CD']}
    report = {'scope': stored['scope'], 'rows':len(d),'panels':len(panels),'components':cols,'solutions':{},'input_sha256':hashes}
    for name, bases in [('both',['xlarge_CD','mean8_CD']),('xlarge',['xlarge_CD'])]:
        s = stored['solutions'][name]
        records = [(label,b) for b in bases for label in panels]
        B = {(label,b):sum((abs(bs[b][int(i)]-y[int(i)]) for i in panels[label]),Q(0)) for label,b in records}
        assert all(v>0 for v in B.values())
        beta = {key:Q(0) for key in records}
        seen=set()
        for row in s['nonzero_panel_beta']:
            key=(row['panel'],row['baseline']); assert key in beta and key not in seen;seen.add(key)
            beta[key]=unpack(row['beta']);assert B[key]==unpack(row['baseline_total_CD'])
        assert all(v>=0 for v in beta.values()) and sum(beta.values(),Q(0))==1
        a=[Q(0)]*len(d)
        for (panel,b),v in beta.items():
            if v:
                for i in panels[panel]:a[int(i)]+=v/B[panel,b]
        u=[Q(0)]*len(d);seen=set()
        for row in s['nonzero_signed_row_weights']:
            i=row['row_index'];assert 0<=i<len(d) and i not in seen;seen.add(i)
            u[i]=unpack(row['u']);assert a[i]==unpack(row['a_bound'])
        assert all(abs(v)<=bound for v,bound in zip(u,a))
        active=sorted(seen)
        costs=[sum((u[i]*p[i][j] for i in active),Q(0)) for j in range(len(cols))]
        target=sum((u[i]*y[i] for i in active),Q(0))
        assert target==unpack(s['target_linear_cost'])
        assert all(v==unpack(s['linear_component_costs'][c]) for c,v in zip(cols,costs))
        upper=1+target-min(costs)
        assert set(s['component_weights'])==set(cols)
        w=[unpack(s['component_weights'][c]) for c in cols]
        assert all(v>=0 for v in w) and sum(w,Q(0))==1
        nz=[j for j,v in enumerate(w) if v]
        error=[abs(sum((w[j]*row[j] for j in nz),Q(0))-yi) for row,yi in zip(p,y)]
        margins={panel+'|'+b:1-sum((error[int(i)] for i in panels[panel]),Q(0))/B[panel,b] for panel,b in records}
        lower=min(margins.values());gap=upper-lower
        assert lower==unpack(s['lower_fraction']) and upper==unpack(s['upper_fraction']) and gap==unpack(s['gap_fraction'])
        assert gap>=0 and upper<Q(9,100)
        dual=FRONT/f'fixed_class_limit/certificate_{name}_highs-ds.npz'
        assert sha(dual)==s['dual_source_sha256']
        report['solutions'][name]={'lower':pack(lower),'upper':pack(upper),'gap':pack(gap),'lower_percent':float(lower*100),'upper_percent':float(upper*100),'gap_percentage_points':float(gap*100),'all_stored_rationals_identical':True,'beta_simplex_and_signed_row_bounds_exact':True,'nine_percent_excluded':True,'panel_margins':{k:pack(v) for k,v in margins.items()},'dual_source_sha256':sha(dual)}
        print(name,report['solutions'][name]['upper_percent'],flush=True)
    assert sha(FRONT/'exact_certificate.py')==stored['script_sha256']
    numerical=json.loads((FRONT/'fixed_class_limit/report.json').read_text())
    if 'input_sha256' in numerical: assert numerical['input_sha256']==hashes
    assert sha(FRONT/'fixed_class_limit.py')==numerical['script_sha256']
    assert sha(FEAS/'solve_feasibility.py')==numerical['helper_sha256']
    for filename,expected in hashes.items():assert sha(filename)==expected
    sources=[Path(__file__),path,FRONT/'exact_certificate.py',FRONT/'fixed_class_limit/report.json',FEAS/'solve_feasibility.py']
    report.update(status='PASS independent exact witness replay; no optimizer invoked',seconds=time.monotonic()-started,provenance_sha256={str(p):sha(p) for p in sources})
    (HERE/'exact_replay.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
