"""Synthetic-only independent adapter invariants and exact Hoeffding checks."""
from pathlib import Path
from fractions import Fraction as F
import ast, hashlib, json, math, types, traceback, time
import numpy as np
HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]/'kl_confidence_production/confidence.py'
raw=SRC.read_bytes();c=types.ModuleType('reviewed_production');c.__file__=str(SRC);exec(compile(raw,str(SRC),'exec'),c.__dict__)
def down(x):
    y=float(x)
    if F(y)>x:y=float(np.nextafter(y,-np.inf))
    assert F(y)<=x;return y
def independent_h(v,b):
    if not b:return F(0),1.
    if not v:u=b
    else:
        def part(z):return 2*sum((z**(2*i+1)/F(2*i+1) for i in range(128)),F(0))+2*z**257/(257*(1-z*z))
        x=(part(F(1,9))+4*part(F(1,3)))/(2*len(v));d=2**256;n=math.isqrt(x.numerator*d*d//x.denominator)
        if n*n*x.denominator<x.numerator*d*d:n+=1
        u=min(b,sum(v,F(0))/len(v)+b*F(n,d))
    return u,down(min(F(1),F(1,100)/u))
def main():
    start=time.monotonic();records=[];checks=0
    original=next(n for n in ast.parse(c.kl_raw).body if isinstance(n,ast.FunctionDef) and n.name=='upper_root')
    digest=hashlib.sha256(ast.dump(ast.Module(body=original.body[1:],type_ignores=[]),include_attributes=False).encode()).hexdigest();assert digest==c.ROOT_AST
    cases=[([],F(0)),([F(0)],F(0)),([],F(1,2)),([],F(1,1000))]
    cases += [([b*q]*m,b) for b,q,m in [(F(1,2),F(0),1),(F(1,2),F(0),9),(F(1,2),F(0),24),(F(1,1000),F(1,3),9),(F(2)**-800,F(1,2),1),(F(2)**800,F(1,2),9),(F(1,3),F(1),24),(F(1,4),F(1,2**130),24),(F(1,4),F(1)-F(1,2**129),9)]]
    for v,b in cases:
        r=c.calibrate_kl_groups(v,b);hu,ht=independent_h(v,b)
        assert r['matched_hoeffding_upper']==hu and r['matched_hoeffding_t']==ht
        assert 0<=r['upper']<=hu and F(r['t'])>=F(ht) and 0<=r['t']<=1 and F(r['t'])*r['upper']<=F(1,100)
        if b and v:
            w=r['root_witness'];root=w['root_at_upward_mean'];mean=sum(v,F(0))/len(v)
            assert w['mean_exact']==mean and root['q_exact']==mean/b
            assert r['upper']==min(b*root['upper'],hu) and r['t']==down(min(F(1),F(1,100)/r['upper']))
        else:assert r['root_witness'] is None
        for h,endpoint in [(1.,1.25),(1.,.75),(1.,1.),(2.**-500,2.**-501),(2.**500,2.**501)]:
            p=c.n.q.inward_predict(h,endpoint,r['t'])
            if h!=endpoint:assert 0<=(F(p)-F(h))/(F(endpoint)-F(h))<=F(r['t'])
            else:assert p==h
            checks+=1
        records.append({'groups':len(v),'bound_binary_exponent_case':b==F(2)**800 or b==F(2)**-800,'branch':r['branch'],'matched_ordering':True})
    # Unequal rows: proper identity-weighting, including a fallback row in denominator.
    r=c.fit_kl_scalar([1.]*4,[1.25,1.,1.25,1.25],[1.125,1.,1.125,1.125],[1.,1.,1.5,1.],['a','a','a','b'],F(1,4))
    assert r['group_means']=={'a':F(1,24),'b':F(1,8)} and r['exact_mean']==F(1,12)
    assert r['rows']==4 and r['groups']==2
    rejects=0
    for v,b in [([F(1)],F(0)),([F(-1)],F(1)),([F(2)],F(1)),([],F(-1)),([.0],F(1)),([True],F(1)),([],True),([],.5)]:
        try:c.calibrate_kl_groups(v,b)
        except (ValueError,TypeError):rejects+=1
        else:raise AssertionError('invalid exact input accepted')
    return {'status':'PASS','synthetic_only':True,'source_sha256':hashlib.sha256(raw).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'root_body_ast_sha256':digest,'calibration_cases':len(cases)+1,'inward_cases':checks,'invalid_cases_rejected':rejects,'seconds':time.monotonic()-start,'records':records,'scope':'No empirical source arrays, group means or strengths opened. Independent exact Hoeffding arithmetic and budget/ordering checks; root transcendental proof previously reviewed.'}
if __name__=='__main__':
    out=HERE/'KL_PRODUCTION_SYNTHETIC_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'KL_PRODUCTION_SYNTHETIC_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
