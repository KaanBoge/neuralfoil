"""Independent synthetic binary64/rational checks. No project/data/model imports."""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import math
import random
import sys

U = F(1, 2**53)
E = 4*U + 2*U*U
B0 = F(1, 2) + F(3, 2)*U

def rat(x):
    return F.from_float(x)

def clip(x, lo, hi):
    return min(hi, max(lo, x))

def core_case(b, q):
    br, qr = rat(b), rat(q)
    assert 2.**-500 <= b <= 2.**500 and -.5 <= q <= 1.
    s = 1. + q
    product = b*s
    c = min(2.*b, max(.5*b, product))
    cr = rat(c)
    assert c == product
    assert br/2 <= cr <= 2*br
    assert abs(rat(s)-(1+qr)) <= 2*U
    assert abs(cr/br-(1+qr)) <= E
    d = c-b
    assert rat(d) == cr-br
    half_d = .5*d
    assert rat(half_d) == (cr-br)/2
    h = b+half_d
    hr = rat(h)
    assert abs(hr-(br+cr)/2) <= F(3,2)*U*br
    lo, hi = clip(qr-E,F(-1,2),F(1)), clip(qr+E,F(-1,2),F(1))
    bound = max(abs(lo),abs(hi))/2 + F(3,2)*U
    assert abs(cr-hr)/br <= bound <= B0
    assert math.isfinite(c) and math.isfinite(h) and c > 0 and h > 0
    return br, cr, hr, c, h

def inward(h, c, t):
    p = h+t*(c-h)
    hr, cr, tr = rat(h),rat(c),rat(t)
    steps = 0
    while True:
        pr = rat(p)
        theta = F(0) if cr == hr and pr == hr else (pr-hr)/(cr-hr)
        if 0 <= theta <= tr:
            return p, theta, steps
        p = math.nextafter(p,h)
        steps += 1
        if steps > 8:
            raise AssertionError('Synthetic inward construction exceeded diagnostic limit')

def endpoint_loss(c,h,y,b):
    return max(abs(c-y)-abs(h-y),F(0))/b

def log_enclosure(x, terms=128):
    z=(x-1)/(x+1)
    assert 0 < z < 1
    lower=2*sum((z**(2*k+1)/F(2*k+1) for k in range(terms)),F(0))
    tail=2*z**(2*terms+1)/(F(2*terms+1)*(1-z*z))
    return lower, lower+tail

def sqrt_upper(x):
    assert x>=0
    den=2**256
    n=x.numerator*den*den
    d=x.denominator
    a=math.isqrt(n//d)
    if a*a*d<n:
        a+=1
    out=F(a,den)
    assert out*out>=x
    assert a==0 or F(a-1,den)**2 < x
    return out

def down_float(x):
    y=float(x)
    while rat(y)>x:
        y=math.nextafter(y,0.)
    assert rat(y)<=x
    return y

def main():
    if len(sys.argv)!=2:
        raise SystemExit('Supply one new output JSON path')
    out=Path(sys.argv[1])
    if out.exists():
        raise SystemExit('Refusing existing output')
    rng=random.Random(2026090837)
    bs=[2.**-500,math.nextafter(2.**-500,math.inf),1.,math.nextafter(1.,0.),math.nextafter(1.,math.inf),math.nextafter(2.**500,0.),2.**500]
    qs=[-.5,math.nextafter(-.5,0.),0.,math.nextafter(0.,1.),math.nextafter(0.,-1.),math.nextafter(1.,0.),1.]
    cases=[(b,q) for b in bs for q in qs]
    cases += [(math.ldexp(1.+rng.random(),rng.randrange(-500,500)),1.5*rng.random()-.5) for _ in range(2000)]
    interventions=0
    max_steps=0
    loss_checks=0
    for b,q in cases:
        br,cr,hr,c,h=core_case(b,q)
        for t in [0.,math.nextafter(0.,1.),.01,.1,.5,math.nextafter(1.,0.),1.]:
            p,theta,steps=inward(h,c,t)
            max_steps=max(max_steps,steps)
            interventions += steps>0
            for y in [F(0),hr,cr,(hr+cr)/2,rat(sys.float_info.max),-rat(sys.float_info.max)]:
                lc=endpoint_loss(cr,hr,y,br)
                lp=endpoint_loss(rat(p),hr,y,br)
                assert lc<=B0
                assert lp <= rat(t)*lc
                loss_checks+=1
    l2,u2=log_enclosure(F(2))
    l54,u54=log_enclosure(F(5,4))
    log20lo,log20hi=4*l2+l54,4*u2+u54
    # Tail enclosure nesting is independent of libm's log approximation.
    l2long,u2long=log_enclosure(F(2),160)
    l54long,u54long=log_enclosure(F(5,4),160)
    assert log20lo < 4*l2long+l54long <= 4*u2long+u54long < log20hi
    confidence_checks=0
    for m in [1,2,16,24,100,10000]:
        penalty=sqrt_upper(log20hi/F(2*m))
        for bound in [F(1,10),F(1,3),B0]:
            for proportion in [F(0),F(1,10),F(1,2),F(1)]:
                mean=proportion*bound
                upper=min(bound,mean+bound*penalty)
                t_exact=min(F(1),F(1,100)/upper)
                tf=down_float(t_exact)
                assert rat(tf)*upper<=F(1,100)
                confidence_checks+=1
    result={'status':'PASS','scope':'Synthetic only; no outcomes, calibration arrays or model execution',
            'seed':2026090837,'core_cases':len(cases),'exact_loss_projection_checks':loss_checks,
            'synthetic_inward_adjustment_cases':interventions,'maximum_observed_inward_steps':max_steps,
            'confidence_algebra_cases':confidence_checks,'python':sys.version,
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'limitations':'Synthetic checks support but do not replace the domain proof or authenticate any model/runtime.'}
    with out.open('x') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
