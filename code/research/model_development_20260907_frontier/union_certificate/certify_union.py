"""Exact rational sandwich certificate for the 30-column fallback-aware union."""
from pathlib import Path
from fractions import Fraction as F
import hashlib
import json
import sys
import time
import warnings
import numpy as np
from scipy.optimize import linprog, OptimizeWarning

HERE=Path(__file__).resolve().parent
FRONT=HERE.parent
sys.path.insert(0,str(FRONT))
import union_calibration as union
import fixed_class_limit as numeric


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pack(x):return {"numerator":str(x.numerator),"denominator":str(x.denominator)}
def array_hash(a):return hashlib.sha256(np.ascontiguousarray(a,dtype="<f8").tobytes()).hexdigest()


def numerical_solve(d,components,panels,baselines,name,method):
    started=time.monotonic()
    c,a,b,eq,rhs,lo,hi,records=numeric.problem(d,components,panels,baselines)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=OptimizeWarning,message="Unrecognized options detected")
        result=linprog(c,A_ub=a,b_ub=b,A_eq=eq,b_eq=rhs,bounds=list(zip(lo,hi)),method=method,
                      options={"threads":1,"primal_feasibility_tolerance":1e-9,"dual_feasibility_tolerance":1e-9,"ipm_optimality_tolerance":1e-10})
    assert result.success,result.message
    w=np.maximum(result.x[:len(components)],0);w/=w.sum()
    prediction=d[components].to_numpy()@w
    metrics=union.old.metrics(d,prediction,panels,name)
    margin=min(float(metrics[baseline+"_improvement_percent"].min())/100 for baseline in baselines)
    residual=float(np.max(a@result.x-b))
    assert residual<1e-6
    np.testing.assert_allclose(eq@result.x,rhs,atol=1e-9)
    dest=HERE/f"numeric_{name}_{method}.npz"
    np.savez_compressed(dest,primal=result.x,inequality_dual=result.ineqlin.marginals,equality_dual=result.eqlin.marginals,
                        lower_bounds=lo,upper_bounds=hi,weights=w,prediction_CD=prediction)
    metrics.to_csv(HERE/f"numeric_metrics_{name}_{method}.csv",index=False)
    record={"method":method,"weights":dict(zip(components,map(float,w))),"actual_min_improvement_fraction":margin,
            "primal_max_inequality_violation":residual,"seconds":time.monotonic()-started,"iterations":int(result.nit),
            "dual_source_sha256":sha(dest)}
    prior=FRONT/"union_calibration"/f"blend_{name}.json"
    if prior.exists():
        previous=json.loads(prior.read_text())
        difference=margin-previous["actual_min_improvement_fraction"]
        assert abs(difference)<1e-7,(name,difference)
        record.update(root_blend_sha256=sha(prior),root_margin_difference_fraction=difference)
    (HERE/f"numeric_{name}_{method}.json").write_text(json.dumps(record,indent=2)+"\n")
    print(json.dumps({"stage":"numerical","objective":name,"margin_percent":margin*100,"seconds":record["seconds"]}),flush=True)
    return record,result.ineqlin.marginals,dest


def exact_witness(p,y,baseline_errors,components,panels,baselines,numerical,dual):
    start=time.monotonic();n=len(y);k=len(components)
    records=[(name,baseline,list(map(int,idx))) for baseline in baselines for name,idx in panels.items()]
    denominators=[sum((baseline_errors[b][i] for i in ix),F(0)) for _,b,ix in records]
    assert all(x>0 for x in denominators)
    q=[F(float(v)) for v in dual]
    assert len(q)==2*n+len(records)
    proposed=[max(-v,F(0)) for v in q[2*n:]]
    total=sum(proposed,F(0));assert total>0
    beta=[v/total for v in proposed]
    assert sum(beta,F(0))==1 and all(v>=0 for v in beta)
    a=[F(0)]*n
    for weight,denominator,(_,_,ix) in zip(beta,denominators,records):
        if weight:
            value=weight/denominator
            for i in ix:a[i]+=value
    u=[max(-a[i],min(a[i],10000*(-q[i]+q[n+i])/total)) for i in range(n)]
    assert all(abs(v)<=bound for v,bound in zip(u,a))
    active=[i for i,v in enumerate(u) if v]
    costs=[sum((u[i]*p[i][j] for i in active),F(0)) for j in range(k)]
    target=sum((u[i]*y[i] for i in active),F(0))
    upper=1+target-min(costs)
    w=[max(F(float(numerical["weights"][c])),F(0)) for c in components]
    total=sum(w,F(0));assert total>0
    w=[v/total for v in w]
    assert all(v>=0 for v in w) and sum(w,F(0))==1
    used=[j for j,v in enumerate(w) if v]
    errors=[abs(sum((w[j]*row[j] for j in used),F(0))-yi) for row,yi in zip(p,y)]
    margins=[1-sum((errors[i] for i in ix),F(0))/denominator for (_,_,ix),denominator in zip(records,denominators)]
    lower=min(margins);gap=upper-lower
    assert gap>=0
    threshold=F(9,100)
    decision="feasible" if lower>=threshold else ("impossible" if upper<threshold else "unresolved")
    return {"lower_fraction":pack(lower),"upper_fraction":pack(upper),"gap_fraction":pack(gap),
            "lower_percent_display":float(100*lower),"upper_percent_display":float(100*upper),"gap_percentage_points_display":float(100*gap),
            "gap_below_1e_8_percentage_points":gap<F(1,10**10),"nine_percent_in_this_frozen_class":decision,
            "component_weights":{c:pack(v) for c,v in zip(components,w)},
            "nonzero_panel_beta":[{"panel":records[j][0],"baseline":records[j][1],"beta":pack(v),"baseline_total_CD":pack(denominators[j])} for j,v in enumerate(beta) if v],
            "nonzero_signed_row_weights":[{"row_index":i,"u":pack(u[i]),"a_bound":pack(a[i])} for i in active],
            "linear_component_costs":{c:pack(v) for c,v in zip(components,costs)},"target_linear_cost":pack(target),
            "exact_panel_margins":[{"panel":r[0],"baseline":r[1],"margin_fraction":pack(v)} for r,v in zip(records,margins)],
            "seconds":time.monotonic()-start,"dual_source_sha256":numerical["dual_source_sha256"]}


def main():
    assert not (HERE/"exact_report.json").exists(),"Preserve completed certificate"
    d,components,aliases,hashes=union.get_data();panels=union.old.panels(d)
    assert len(components)==30 and len(panels)==23 and len(d)==29856
    matrix=d[components].to_numpy();targets=d.measured_CD.to_numpy()
    assert np.isfinite(matrix).all() and np.isfinite(targets).all()
    source_paths=[Path(__file__),HERE/"PROTOCOL.md",Path(union.__file__),Path(numeric.__file__),Path(union.assessment.__file__),Path(union.old.__file__)]
    provenance={str(p):sha(p) for p in source_paths}
    report={"scope":"Exact parsed-binary-float retrospective bound for 30 frozen global convex components on 23 panels; not universal",
            "inference_convention":"All25 external gate-false rows replaced with mean8 in every component alias; original baselines unchanged",
            "arithmetic":"Fraction(float) before subtraction/multiplication; decimal displays approximate exact stored fractions",
            "rows":len(d),"components":components,"component_aliases":aliases,"panels":list(panels),"input_sha256":hashes,
            "source_sha256":provenance,"actual_array_sha256":{"P_float64_little_endian":array_hash(matrix),"y_float64_little_endian":array_hash(targets),
                **{b:array_hash(d[b].to_numpy()) for b in ["xlarge_CD","mean8_CD"]}},"solutions":{}}
    (HERE/"started_manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    # Convert each raw parsed scalar before arithmetic, not rounded differences.
    p=[[F(float(v)) for v in row] for row in matrix]
    y=[F(float(v)) for v in targets]
    be={b:[abs(F(float(v))-yi) for v,yi in zip(d[b],y)] for b in ["xlarge_CD","mean8_CD"]}
    for name,baselines in [("both",["xlarge_CD","mean8_CD"]),("xlarge",["xlarge_CD"])]:
        for method in ["highs-ipm","highs-ds"]:
            numerical,dual,path=numerical_solve(d,components,panels,baselines,name,method)
            exact=exact_witness(p,y,be,components,panels,baselines,numerical,dual)
            exact.update(method=method,numerical=numerical)
            (HERE/f"witness_{name}_{method}.json").write_text(json.dumps(exact,indent=2)+"\n")
            print(json.dumps({"stage":"exact","objective":name,**{k:exact[k] for k in ["lower_percent_display","upper_percent_display","gap_percentage_points_display","nine_percent_in_this_frozen_class","seconds"]}}),flush=True)
            if exact["gap_below_1e_8_percentage_points"]:break
        report["solutions"][name]=exact
    assert all(sha(p)==digest for p,digest in hashes.items())
    assert all(sha(p)==digest for p,digest in provenance.items())
    (HERE/"exact_report.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":main()
