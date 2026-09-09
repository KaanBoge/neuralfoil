"""Independent exact-rational inward interpolation; no production imports/I/O."""
import math
from fractions import Fraction as F
def prediction(base,core,anchor,gate,t):
    if type(gate) is not bool or type(t) is not float or not math.isfinite(t) or not 0<=t<=1:raise ValueError('gate/strength')
    if not all(math.isfinite(x) and x>0 for x in (base,core,anchor)):raise ValueError('finite positive endpoints')
    if not gate:return base,0.0
    if core==anchor:return anchor,0.0
    c,h,tf=F(core),F(anchor),F(t);ideal=h+tf*(c-h);p=float(ideal)
    # Rounding is inward towards anchor, independently of native vector code.
    if (c>h and F(p)>ideal) or (c<h and F(p)<ideal):p=math.nextafter(p,anchor)
    effective=(F(p)-h)/(c-h)
    if not 0<=effective<=tf:raise ValueError('exact effective-fraction bound')
    return p,float(effective)
