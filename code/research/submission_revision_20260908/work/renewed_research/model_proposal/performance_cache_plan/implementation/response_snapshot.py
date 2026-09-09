"""Private immutable snapshots; consumers receive independent complete copies."""
from types import MappingProxyType
import numpy as np

def seal(value):
    if isinstance(value,np.ndarray):
        if value.dtype.hasobject:raise ValueError('object response array')
        out=value.copy(order='K');out.flags.writeable=False
        return ('array',out)
    if isinstance(value,dict):return ('dict',MappingProxyType({k:seal(v) for k,v in value.items()}))
    if isinstance(value,list):return ('list',tuple(seal(v) for v in value))
    if isinstance(value,tuple):return ('tuple',tuple(seal(v) for v in value))
    if value is None or isinstance(value,(str,bool,int,float,np.generic)):return ('scalar',value)
    raise ValueError('unsupported response value type')
def unseal(node):
    kind,value=node
    if kind=='array':return value.copy(order='K')
    if kind=='dict':return {k:unseal(v) for k,v in value.items()}
    if kind=='list':return [unseal(v) for v in value]
    if kind=='tuple':return tuple(unseal(v) for v in value)
    return value
class ResponseSnapshot:
    __slots__=('_payload',)
    def __init__(self,response):
        if not isinstance(response,dict):raise ValueError('complete response dictionary required')
        self._payload=seal(response)
    def copy(self):return unseal(self._payload)
