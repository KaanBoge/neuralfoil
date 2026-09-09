"""Label-free exact-enclosure prototype. No I/O, model or calibration loading."""
from fractions import Fraction as F
from functools import lru_cache

TERMS = 128
Q_BITS = 128
STEPS = 64


def _rational(value):
    if isinstance(value, bool) or not isinstance(value, (F, int)):
        raise TypeError('exact Fraction or integer required')
    return F(value)


def series_log(z):
    """Enclose log((1+z)/(1-z)) by a positive rational series and tail."""
    z = _rational(z)
    if not 0 <= z <= F(1, 3):
        raise ValueError('range-reduced series input required')
    if not z:
        return F(0), F(0)
    zz = z*z
    term = z
    total = F(0)
    for k in range(TERMS):
        total += term/(2*k+1)
        term *= zz
    lower = 2*total
    return lower, lower + 2*term/((2*TERMS+1)*(1-zz))


@lru_cache(maxsize=1)
def log2_interval():
    return series_log(F(1, 3))


def log_interval(value):
    """Exact sign-correct logarithm enclosure for a positive rational."""
    value = _rational(value)
    if value <= 0:
        raise ValueError('positive logarithm argument required')
    k = value.numerator.bit_length() - value.denominator.bit_length()
    scale = F(2**k) if k >= 0 else F(1, 2**(-k))
    s = value/scale
    if s < 1:
        k -= 1
        s *= 2
    if not 1 <= s < 2:
        raise ArithmeticError('exact range reduction failed')
    lo, hi = series_log((s-1)/(s+1))
    a, b = log2_interval()
    return (lo+k*a, hi+k*b) if k >= 0 else (lo+k*b, hi+k*a)


def kl_interval(q, u):
    """Enclose Bernoulli KL; fractional losses need not be Bernoulli."""
    q, u = _rational(q), _rational(u)
    if not 0 <= q <= u < 1:
        raise ValueError('0 <= q <= u < 1 required')
    if q == u:
        return F(0), F(0)
    positive_lo, positive_hi = log_interval((1-q)/(1-u))
    if q == 0:
        return positive_lo, positive_hi
    negative_lo, negative_hi = log_interval(q/u)
    return (q*negative_lo + (1-q)*positive_lo,
            q*negative_hi + (1-q)*positive_hi)


def ceil_mean(q):
    q = _rational(q)
    if not 0 <= q <= 1:
        raise ValueError('normalized mean outside [0,1]')
    scale = 2**Q_BITS
    k = (q.numerator*scale + q.denominator-1)//q.denominator
    upper = F(k, scale)
    if not q <= upper <= 1 or not upper-q < F(1, scale):
        raise ArithmeticError('upward mean enclosure failed')
    return upper


def upper_root(q, groups):
    """Synthetic-only input contract; exact conservative root bracket."""
    q = _rational(q)
    if isinstance(groups, bool) or not isinstance(groups, int) or groups <= 0:
        raise ValueError('positive integer group count required')
    qu = ceil_mean(q)
    log_lo, log_hi = log_interval(F(20))
    budget_lo, budget_hi = log_lo/groups, log_hi/groups
    lo, hi = qu, F(1)
    low_witness = (F(0), F(0))
    high_witness = None
    iterations = 0
    stop = 'deterministic_endpoint' if qu == 1 else 'step_limit'
    if qu < 1:
        for step in range(STEPS):
            trial = (lo+hi)/2
            lower, upper = kl_interval(qu, trial)
            iterations = step+1
            if lower >= budget_hi:
                hi = trial
                high_witness = (lower, upper)
            elif upper <= budget_lo:
                lo = trial
                low_witness = (lower, upper)
            else:
                stop = 'unresolved_interval_preserved_bracket'
                break
    if not q <= qu <= lo <= hi <= 1:
        raise ArithmeticError('root ordering failed')
    if qu < 1 and low_witness[1] > budget_lo:
        raise ArithmeticError('left endpoint certificate failed')
    if high_witness is not None and high_witness[0] < budget_hi:
        raise ArithmeticError('right endpoint certificate failed')
    if hi != 1 and high_witness is None:
        raise ArithmeticError('missing finite right certificate')
    return {'q_exact': q, 'q_upper': qu, 'q_rounding_gap': qu-q,
            'groups': groups, 'lower': lo, 'upper': hi,
            'budget_lower': budget_lo, 'budget_upper': budget_hi,
            'lower_kl_interval': low_witness, 'upper_kl_interval': high_witness,
            'iterations': iterations, 'stop': stop}
