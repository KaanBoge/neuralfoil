"""Independent review arithmetic; authenticated prior reviewer definitions only.

No scientific payload access. Loading explicitly extracts selected pure function
ASTs, not module initialization or main; no producer arithmetic is imported.
"""
import ast,math
from fractions import Fraction as F
from pathlib import Path
import audit_common as ac
BASE=Path(__file__).resolve().parent.parent
SOURCES={
 'audit_kl_illustration.py':('5acdb446b386eebbce702bb6ca3a98d5fda968d77a94f2ee021c17aaadff25ac',('log_interval','kl_interval','down')),
 'stage1_v2_audit/audit_scalars.py':('96b9e685d78dd0d2ccacf7ea3e896578d83fa9557c54580e937ae38134db5d5d',('log_upper','sqrt_upper'))}
def load(access):
    import numpy as np
    ns={'F':F,'np':np,'math':math}
    for name,(pin,names) in SOURCES.items():
        raw=access.read(BASE/name,pin)
        tree=ast.parse(raw);chosen=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        if [n.name for n in chosen]!=list(names):raise ValueError('pure reviewer function inventory')
        exec(compile(ast.Module(body=chosen,type_ignores=[]),name,'exec'),ns)
    return ns
def decode(v):
    if isinstance(v,dict):
        if 'encoding' in v and 'numerator' in v:return ac.decode(v)
        return {k:decode(x) for k,x in v.items()}
    if isinstance(v,list):return [decode(x) for x in v]
    return v
def verify(s,B,mean,means,rows,kind,maths):
    """Exact endpoint verification, not a fresh bisection or loss selection.

    This fixed-study audit deliberately fails closed for unobserved degenerate
    contexts rather than silently inventing a boundary witness interpretation.
    """
    m=len(means)
    if not (m>0 and B>0 and 0<=mean<B):raise ValueError('fixed nondegenerate witness scope')
    assert s['group_means']==means and s['exact_mean']==mean and s['bound']==B
    assert type(s['rows']) is int and s['rows']==rows and type(s['groups']) is int and s['groups']==m
    H=min(B,mean+B*maths['sqrt_upper'](maths['log_upper']()/(2*m)))
    th=maths['down'](min(F(1),F(1,100)/H));U=H
    if kind=='KL':
        assert s['matched_hoeffding_upper']==H and s['matched_hoeffding_t']==th
        w=s['root_witness'];r=w['root_at_upward_mean'];q=mean/B
        qu=F((q.numerator*2**128+q.denominator-1)//q.denominator,2**128)
        assert r['q_exact']==q and r['q_upper']==qu and r['q_rounding_gap']==qu-q and r['groups']==m
        loglo,loghi=maths['log_interval'](F(20))
        assert r['budget_lower']==loglo/m and r['budget_upper']==loghi/m
        lo,hi=r['lower'],r['upper'];assert qu<=lo<=hi<=1
        assert r['iterations']==64 and r['stop']=='step_limit' and hi-lo==(1-qu)/2**64
        li=maths['kl_interval'](qu,lo)
        assert list(li)==r['lower_kl_interval'] and li[1]<=loglo/m
        if hi<1:
            ui=maths['kl_interval'](qu,hi)
            assert list(ui)==r['upper_kl_interval'] and ui[0]>=loghi/m
        else:assert r['upper_kl_interval'] is None
        assert w['mean_exact']==mean and w['kl_upper_before_hoeffding_min']==B*hi
        assert w['lower_endpoint_scope']=='root_at_q_upper_only' and w['upper_endpoint_scope']=='conservative_for_q_exact'
        U=min(B*hi,H)
    elif kind!='H':raise ValueError('fixed H or KL only')
    t=maths['down'](min(F(1),F(1,100)/U))
    assert s['upper']==U and type(s['t']) is float and s['t']==t and F(t)*U<=F(1,100)
    if kind=='KL':assert s['conditional_not_certified'] is True
    return U,t
