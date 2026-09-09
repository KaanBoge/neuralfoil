"""Private immutable component charges; never a general object-ID cache."""
from dataclasses import dataclass
import sys
from pilot_engine_v2 import owned_size


class FrozenMap(tuple):
    __slots__=()
    def __getitem__(self,key):
        for k,v in tuple.__iter__(self):
            if k==key:return v
        raise KeyError(key)


class FrozenList(tuple):
    __slots__=()


def freeze(x):
    if isinstance(x,FrozenMap):return FrozenMap((freeze(k),freeze(v)) for k,v in tuple.__iter__(x))
    if isinstance(x,FrozenList):return FrozenList(freeze(v) for v in x)
    if type(x) is dict:return FrozenMap((freeze(k),freeze(v)) for k,v in x.items())
    if type(x) is list:return FrozenList(freeze(v) for v in x)
    if type(x) is tuple:return tuple(freeze(v) for v in x)
    if type(x) in (str,int,float,bool,type(None)):return x
    raise TypeError('unsupported mutable component')


def thaw(x):
    if isinstance(x,FrozenMap):return {thaw(k):thaw(v) for k,v in tuple.__iter__(x)}
    if isinstance(x,FrozenList):return [thaw(v) for v in x]
    if type(x) is tuple:return tuple(thaw(v) for v in x)
    return x


@dataclass(frozen=True,slots=True)
class Sealed:
    value: object
    charge: int

    def __post_init__(self):
        def check(x):
            if isinstance(x,(FrozenMap,FrozenList)) or type(x) is tuple:
                return all(check(v) for v in tuple.__iter__(x))
            return type(x) in (str,int,float,bool,type(None))
        if not check(self.value):raise TypeError('component graph is not immutable')
        floor=owned_size(self.value)+owned_size(thaw(self.value))+sys.getsizeof(self)+sys.getsizeof(self.charge)
        if type(self.charge) is not int or self.charge<floor:raise ValueError('insufficient component charge')

    @classmethod
    def make(cls,obj):
        value=freeze(obj)
        # Charge both immutable storage and a complete serialization/reference
        # conversion, including duplicate subgraphs across separate components.
        raw=owned_size(value)+owned_size(thaw(value))+owned_size(obj)
        charge=raw+sys.getsizeof(object.__new__(cls))+sys.getsizeof(raw)+sys.getsizeof(raw+1024)
        return cls(value,charge)

    def __getitem__(self,key):return self.value[key]


class Prefix:
    """Append-only completed-tree tuples. No mutable leaf list escapes."""
    __slots__=('_values','_sum')
    def __init__(self):
        self._values=[];self._sum=0
    def append(self,leaves):
        if any(type(x) is not float for x in leaves):raise TypeError('float leaves')
        item=tuple(leaves)
        # Retain exact incoming list allocation charge and immutable tuple charge.
        charge=owned_size(leaves)+owned_size(item)
        self._values.append(item)
        self._sum+=charge
    def __iter__(self):return iter(self._values)
    def charge(self):
        return self._sum+sys.getsizeof(self)+sys.getsizeof(self._values)+sys.getsizeof(self._sum)
    def reference(self):
        # Recreate append-built containers, including normal list over-allocation.
        out=[]
        for values in self._values:
            row=[]
            for v in values:row.append(v)
            out.append(row)
        return out
