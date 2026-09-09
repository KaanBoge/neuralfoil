"""Optimizer-free exact witness replay from stored rationals and source arrays."""
from pathlib import Path
from fractions import Fraction as Q
import hashlib
import json
import sys
import warnings
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import union_calibration as union


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unpack(v):return Q(int(v["numerator"]),int(v["denominator"]))
def array_hash(a):return hashlib.sha256(np.ascontiguousarray(a,dtype="<f8").tobytes()).hexdigest()


def main():
    stored=json.loads((HERE/"exact_report.json").read_text())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",pd.errors.PerformanceWarning)
        d,components,aliases,hashes=union.get_data()
    assert hashes==stored["input_sha256"] and components==stored["components"] and aliases==stored["component_aliases"]
    assert len(components)==30 and len(d)==29856
    panels=union.old.panels(d);assert list(panels)==stored["panels"]
    assert array_hash(d[components].to_numpy())==stored["actual_array_sha256"]["P_float64_little_endian"]
    assert array_hash(d.measured_CD.to_numpy())==stored["actual_array_sha256"]["y_float64_little_endian"]
    p=[[Q(float(v)) for v in row] for row in d[components].to_numpy()]
    y=[Q(float(v)) for v in d.measured_CD]
    baseline={b:[Q(float(v)) for v in d[b]] for b in ["xlarge_CD","mean8_CD"]}
    for b in baseline:assert array_hash(d[b].to_numpy())==stored["actual_array_sha256"][b]
    outcomes={}
    for name,bases in [("both",["xlarge_CD","mean8_CD"]),("xlarge",["xlarge_CD"])]:
        s=stored["solutions"][name]
        keys=[(panel,b) for b in bases for panel in panels]
        B={(panel,b):sum((abs(baseline[b][int(i)]-y[int(i)]) for i in panels[panel]),Q(0)) for panel,b in keys}
        assert all(v>0 for v in B.values())
        beta={k:Q(0) for k in keys};seen=set()
        for r in s["nonzero_panel_beta"]:
            key=(r["panel"],r["baseline"]);assert key in beta and key not in seen;seen.add(key)
            beta[key]=unpack(r["beta"]);assert B[key]==unpack(r["baseline_total_CD"])
        assert sum(beta.values(),Q(0))==1 and all(v>=0 for v in beta.values())
        a=[Q(0)]*len(d)
        for (panel,b),v in beta.items():
            if v:
                for i in panels[panel]:a[int(i)]+=v/B[panel,b]
        u=[Q(0)]*len(d);seen=set()
        for r in s["nonzero_signed_row_weights"]:
            i=r["row_index"];assert 0<=i<len(d) and i not in seen;seen.add(i)
            u[i]=unpack(r["u"]);assert a[i]==unpack(r["a_bound"])
        assert all(abs(v)<=bound for v,bound in zip(u,a))
        active=sorted(seen)
        costs=[sum((u[i]*p[i][j] for i in active),Q(0)) for j in range(len(components))]
        target=sum((u[i]*y[i] for i in active),Q(0))
        assert target==unpack(s["target_linear_cost"])
        assert all(v==unpack(s["linear_component_costs"][c]) for c,v in zip(components,costs))
        upper=1+target-min(costs)
        w=[unpack(s["component_weights"][c]) for c in components]
        assert all(v>=0 for v in w) and sum(w,Q(0))==1
        used=[j for j,v in enumerate(w) if v]
        errors=[abs(sum((w[j]*row[j] for j in used),Q(0))-yi) for row,yi in zip(p,y)]
        margins={(panel,b):1-sum((errors[int(i)] for i in panels[panel]),Q(0))/B[panel,b] for panel,b in keys}
        for r in s["exact_panel_margins"]:assert unpack(r["margin_fraction"])==margins[r["panel"],r["baseline"]]
        lower=min(margins.values());gap=upper-lower
        assert lower==unpack(s["lower_fraction"]) and upper==unpack(s["upper_fraction"]) and gap==unpack(s["gap_fraction"])
        assert gap>=0
        decision="feasible" if lower>=Q(9,100) else ("impossible" if upper<Q(9,100) else "unresolved")
        assert decision==s["nine_percent_in_this_frozen_class"]
        assert sha(HERE/f"numeric_{name}_{s['method']}.npz")==s["dual_source_sha256"]
        assert sha(HERE.parent/"union_calibration"/f"blend_{name}.json")==s["numerical"]["root_blend_sha256"]
        outcomes[name]={"all_rationals_reproduced_exactly":True,"nine_percent_decision":decision,
                        "lower_percent_display":float(lower*100),"upper_percent_display":float(upper*100),"gap_percentage_points_display":float(gap*100)}
    assert all(sha(p)==h for p,h in stored["source_sha256"].items())
    assert all(sha(p)==h for p,h in hashes.items())
    report={"status":"PASS optimizer-free exact witness replay","solutions":outcomes,"script_sha256":sha(__file__),"certificate_sha256":sha(HERE/"exact_report.json")}
    (HERE/"replay_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
