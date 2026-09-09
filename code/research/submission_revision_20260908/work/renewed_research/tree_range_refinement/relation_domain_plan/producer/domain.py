"""Restricted numeric domain and explicit runtime identity fallback."""
import math
import struct
import sys

GUARD_SHA256='1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127'


def stamp():
    return {'id':'FINITE_X62_ABS_MINMAX_NUMERIC_V1','dimensions':62,
            'relations':['X16=abs(X0)','X18=min(X12,X13)','X19=max(X12,X13)'],
            'equality':'numeric_signed_zero_equal','finite_binary64':True,
            'guard_source_sha256':GUARD_SHA256}


def assert_binary64():
    if not (sys.float_info.radix==2 and sys.float_info.mant_dig==53 and
            sys.float_info.max_exp==1024 and struct.calcsize('d')==8):
        raise RuntimeError('binary64 runtime required before relation oracle')


def in_domain(x):
    assert_binary64()
    return (type(x) in (list,tuple) and len(x)==62 and
            all(type(v) is float and math.isfinite(v) for v in x) and
            x[16]==abs(x[0]) and x[18]==min(x[12],x[13]) and x[19]==max(x[12],x[13]))


def guarded_prediction(features,baseline,restricted_prediction,gate,relation_guard):
    """Caller supplies the authenticated root relation_guard; no inference here."""
    assert_binary64()
    if type(gate) is not bool:raise ValueError('Boolean existing gate required')
    if type(baseline) is not float or not math.isfinite(baseline) or baseline<=0:
        raise ValueError('finite positive binary64 baseline')
    if not gate or not relation_guard(features):return baseline
    if not in_domain(features):raise ValueError('guard disagrees with exact numeric domain')
    if type(restricted_prediction) is not float or not math.isfinite(restricted_prediction) or restricted_prediction<=0:
        raise ValueError('finite positive active prediction')
    return restricted_prediction
