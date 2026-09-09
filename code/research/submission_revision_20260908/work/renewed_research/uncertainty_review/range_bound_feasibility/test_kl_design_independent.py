"""Synthetic-only independent diagnostics; no empirical arrays or strengths."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import hashlib, json, types, time, traceback
HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]/'kl_confidence_design/exact_kl.py'
raw=SRC.read_bytes();k=types.ModuleType('reviewed_kl');exec(compile(raw,str(SRC),'exec'),k.__dict__)
def dec(x):return D(x.numerator)/D(x.denominator)
def kl(q,u):return (q*(q/u).ln() if q else D(0))+(1-q)*((1-q)/(1-u)).ln()
def main():
    start=time.monotonic();counts={'log_enclosures':0,'KL_enclosures':0,'root_cases':0,'invalid_inputs':0,'mean_enclosures':0};records=[]
    with localcontext() as ctx:
        ctx.prec=180
        values=[F(1),F(2),F(20),F(1,20),F(17,31)]
        values += [F(2)**e*factor for e in [-1000,-100,-2,-1,0,1,2,100,1000] for factor in [F(1),F(3,2),F(2)-F(1,2**30),F(1)+F(1,2**30)]]
        for x in values:
            lo,hi=k.log_interval(x);truth=dec(x).ln();assert dec(lo)<=truth<=dec(hi);counts['log_enclosures']+=1
        qs=[F(0),F(1,2**130),F(1,32),F(1,3),F(1,2),F(99,100)]
        for q in qs:
            for proportion in [F(1,100),F(1,2),F(99,100)]:
                v=q+(1-q)*proportion;lo,hi=k.kl_interval(q,v);truth=kl(dec(q),dec(v))
                # Rational enclosure may be narrower than Decimal's final rounding.
                assert dec(lo)-D('1e-170')<=truth<=dec(hi)+D('1e-170');counts['KL_enclosures']+=1
        huge=F(2**20000-1,3*2**20000)
        root_qs=qs+[huge,F(1)-F(1,2**129),F(1)]
        for q in root_qs:
            qu=k.ceil_mean(q);assert q<=qu<=1 and qu-q<F(1,2**128);counts['mean_enclosures']+=1
            for m in [1,9,24]:
                r=k.upper_root(q,m);lo,hi=r['lower'],r['upper'];a=D(20).ln()/m
                assert q<=qu<=lo<=hi<=1
                if qu<1:
                    ll,lh=k.kl_interval(qu,lo);assert lh<=r['budget_lower']
                    assert kl(dec(qu),dec(lo))<=a
                if hi<1:
                    hl,hh=k.kl_interval(qu,hi);assert hl>=r['budget_upper'];assert kl(dec(qu),dec(hi))>=a
                # Independent high-precision root only where 180 digits resolve 1-root.
                if qu<=F(99,100):
                    left,right=dec(qu),D(1)
                    for step in range(400):
                        mid=(left+right)/2
                        if kl(dec(qu),mid)<a:left=mid
                        else:right=mid
                    assert dec(lo)<=right and left<=dec(hi)
                    hoeffding=min(D(1),dec(qu)+(a/2).sqrt())
                    assert left<=hoeffding
                records.append({'q_kind':'huge_fraction' if q==huge else str(q),'m':m,'stop':r['stop'],'iterations':r['iterations'],'right_is_one':hi==1})
                counts['root_cases']+=1
        for n in [0,-1,True,1.0,'9']:
            try:k.upper_root(F(1,2),n)
            except (ValueError,TypeError):counts['invalid_inputs']+=1
            else:raise AssertionError('invalid m accepted')
        for q in [True,.5,'1/2',F(-1),F(2)]:
            try:k.upper_root(q,9)
            except (ValueError,TypeError):counts['invalid_inputs']+=1
            else:raise AssertionError('invalid q accepted')
    return {'status':'PASS','synthetic_only':True,'source_sha256':hashlib.sha256(raw).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'decimal_precision':180,'counts':counts,'seconds':time.monotonic()-start,'records':records,'caveat':'Decimal checks are independent diagnostics, not exact transcendental certificates. Exact endpoint inequalities independently rechecked. No calibration data or real strengths accessed.'}
if __name__=='__main__':
    out=HERE/'KL_DESIGN_SYNTHETIC_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        p=HERE/'KL_DESIGN_SYNTHETIC_FAILURE.txt';i=2
        while p.exists():p=HERE/f'KL_DESIGN_SYNTHETIC_FAILURE_{i}.txt';i+=1
        with p.open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({key:value for key,value in r.items() if key!='records'},indent=2))
