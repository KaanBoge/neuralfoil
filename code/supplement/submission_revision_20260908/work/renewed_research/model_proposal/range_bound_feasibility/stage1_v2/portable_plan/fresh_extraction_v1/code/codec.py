from fractions import Fraction as F
from pathlib import Path
import json
def encode(v):
    if isinstance(v,F):
        return {'encoding':'signed-hex-v1', 'numerator':format(v.numerator,'x'),
                'denominator':format(v.denominator,'x')}
    raise TypeError(type(v).__name__)

def fraction(v):
    """Strict canonical tagged hex; authenticated legacy decimal remains readable."""
    import re
    if not isinstance(v,dict):raise ValueError('rational record required')
    if set(v)=={'encoding','numerator','denominator'} and v['encoding']=='signed-hex-v1':
        radix=16;unsigned=r'(?:0|[1-9a-f][0-9a-f]*)';positive=r'[1-9a-f][0-9a-f]*'
    elif set(v)=={'numerator','denominator'}:
        radix=10;unsigned=r'(?:0|[1-9][0-9]*)';positive=r'[1-9][0-9]*'
    else:raise ValueError('unknown rational encoding/schema')
    numerator,denominator=v['numerator'],v['denominator']
    if not isinstance(numerator,str) or not isinstance(denominator,str):raise ValueError('rational strings required')
    if not re.fullmatch(r'-?'+unsigned,numerator) or numerator=='-0' or not re.fullmatch(positive,denominator):
        raise ValueError('noncanonical rational strings')
    a,b=int(numerator,radix),int(denominator,radix)
    result=F(a,b)
    if result.numerator!=a or result.denominator!=b:raise ValueError('rational must be reduced')
    return result

def write_json(path,value):
    # Serialize before touching the destination: codec failures leave no partial file.
    payload=json.dumps(value,default=encode,indent=2,allow_nan=False)+'\n'
    with Path(path).open('x') as f:f.write(payload)
