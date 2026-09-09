"""Independent all-grid rational witness checks; synthetic illustration only."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import hashlib,json,math,traceback,time
import numpy as np
HERE=Path(__file__).resolve().parent
DESIGN=HERE.parents[1]/'kl_confidence_design';SOURCE=DESIGN/'illustration_attempt_1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frac(v):return F(int(v['numerator'],16),int(v['denominator'],16))
def decode(v):
    if isinstance(v,dict):
        if v.get('encoding')=='signed-hex-v1':return frac(v)
        return {k:decode(x) for k,x in v.items()}
    if isinstance(v,list):return [decode(x) for x in v]
    return v
def dec(x):return D(x.numerator)/D(x.denominator)
def log_interval(x):
    power=x.numerator.bit_length()-x.denominator.bit_length();s=x/(F(2)**power)
    if s<1:power-=1;s*=2
    assert 1<=s<2
    def series(z):
        lo=2*sum((z**(2*j+1)/F(2*j+1) for j in range(128)),F(0))
        return lo,lo+2*z**257/(257*(1-z*z))
    a,b=series((s-1)/(s+1));c,d=series(F(1,3))
    return (a+power*c,b+power*d) if power>=0 else (a+power*d,b+power*c)
def kl_interval(q,v):
    if q==v:return F(0),F(0)
    a,b=log_interval((1-q)/(1-v))
    if not q:return a,b
    c,d=log_interval(q/v);return q*c+(1-q)*a,q*d+(1-q)*b
def down(x):
    v=float(x)
    if F(v)>x:v=float(np.nextafter(v,-np.inf))
    return v
def main():
    start=time.monotonic();manifest=json.loads((SOURCE/'MANIFEST.json').read_bytes())
    assert manifest['synthetic_only'] is True and manifest['new_core_fits']==0 and manifest['rows']==51 and manifest['computational_seconds']<180
    for p,h in manifest['input_sha256'].items():assert sha(p)==h
    for p,h in manifest['output_sha256'].items():assert sha(SOURCE/p)==h
    rows=decode(json.loads((SOURCE/'GRID.json').read_bytes()));counts=[1,2,3,4,6,8,9,12,16,24,32,48,64,96,128,192,256]
    assert [(r['q'],r['groups']) for r in rows]==[(q,m) for q in [F(0),F(1,50),F(1,10)] for m in counts]
    loglo,loghi=log_interval(F(20));records=[]
    with localcontext() as ctx:
        ctx.prec=180
        for row in rows:
            q,m,b=row['q'],row['groups'],row['B'];r=row['result'];w=r['root_witness'];root=w['root_at_upward_mean']
            assert b==r['bound']==F(1,2) and r['groups']==m and r['conditional_not_certified'] is True
            assert r['branch']=='bounded_iid_kl_with_certified_hoeffding_min' and w['mean_exact']==b*q
            qu=F((q.numerator*2**128+q.denominator-1)//q.denominator,2**128)
            assert root['q_exact']==q and root['q_upper']==qu and root['q_rounding_gap']==qu-q and root['groups']==m
            assert root['budget_lower']==loglo/m and root['budget_upper']==loghi/m
            lo,hi=root['lower'],root['upper'];assert qu<=lo<=hi<=1
            assert root['iterations']==64 and root['stop']=='step_limit' and hi-lo==(1-qu)/2**64
            lower_interval=kl_interval(qu,lo);assert list(lower_interval)==root['lower_kl_interval'];assert lower_interval[1]<=loglo/m
            if hi<1:
                upper_interval=kl_interval(qu,hi);assert list(upper_interval)==root['upper_kl_interval'];assert upper_interval[0]>=loghi/m
            else:assert root['upper_kl_interval'] is None
            # Diagnostic transcendental check uses the original q, never empirical inputs.
            def dkl(qd,v):return (qd*(qd/v).ln() if qd else D(0))+(1-qd)*((1-qd)/(1-v)).ln()
            if hi<1:assert dkl(dec(q),dec(hi))>=D(20).ln()/m-D('1e-170')
            assert dkl(dec(qu),dec(lo))<=D(20).ln()/m+D('1e-170')
            # Independent unchanged Hoeffding formula uses its original log20 decomposition.
            def orig_part(z):return 2*sum((z**(2*j+1)/F(2*j+1) for j in range(128)),F(0))+2*z**257/(257*(1-z*z))
            x=(orig_part(F(1,9))+4*orig_part(F(1,3)))/(2*m);scale=2**256;n=math.isqrt(x.numerator*scale*scale//x.denominator)
            if n*n*x.denominator<x.numerator*scale*scale:n+=1
            h=min(b,b*q+b*F(n,scale));u=min(b*hi,h)
            assert r['matched_hoeffding_upper']==h and r['matched_hoeffding_t']==down(min(F(1),F(1,100)/h))
            assert w['kl_upper_before_hoeffding_min']==b*hi and r['upper']==u and r['t']==down(min(F(1),F(1,100)/u))
            assert F(r['t'])*u<=F(1,100) and r['t']>=r['matched_hoeffding_t']
            assert w['lower_endpoint_scope']=='root_at_q_upper_only' and w['upper_endpoint_scope']=='conservative_for_q_exact'
            records.append({'q':float(q),'m':m,'KL_U_over_B':float(u/b),'Hoeffding_U_over_B':float(h/b),'KL_t':r['t'],'Hoeffding_t':r['matched_hoeffding_t'],'exact_witnesses_pass':True})
    return {'status':'PASS','synthetic_only':True,'grid_sha256':sha(SOURCE/'GRID.json'),'manifest_sha256':sha(SOURCE/'MANIFEST.json'),'audit_sha256':sha(__file__),'cases':51,'decimal_precision':180,'seconds':time.monotonic()-start,'records':records,'scope':'All prescribed grid fields and exact endpoint witnesses checked, not a regenerated figure or empirical calibration.'}
if __name__=='__main__':
    out=HERE/'KL_ILLUSTRATION_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'KL_ILLUSTRATION_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
