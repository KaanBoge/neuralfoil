"""Small structural allocation probes, not the full135k cold gate or RSS."""
import sys,unittest
from fractions import Fraction as F
import numpy as np
import producer as p
import fixtures as f
def deep(value,seen=None):
    if seen is None:seen=set()
    if id(value) in seen:return 0
    seen.add(id(value));n=sys.getsizeof(value)
    if isinstance(value,dict):n+=sum(deep(k,seen)+deep(v,seen) for k,v in value.items())
    elif isinstance(value,(tuple,list)):n+=sum(deep(v,seen) for v in value)
    elif isinstance(value,F):n+=deep(value.numerator,seen)+deep(value.denominator,seen)
    elif isinstance(value,np.ndarray) and value.base is not None:n+=deep(value.base,seen)
    return n
class Tests(unittest.TestCase):
    def test_worst_limb_encoded_rational_reserve(self):
        values=[p.encode(F(2**4095-1-2*i,2**4095+1)) for i in range(80)]
        self.assertLess(deep(values),240000)
    def test_full_path_edge_charge(self):
        edges=[[i,61,float(sys.float_info.max).hex(),i%2] for i in range(14)]
        leaf={'leaf':28,'value':float(-sys.float_info.max).hex(),'edges':edges,'empty':False}
        self.assertLess(deep(leaf),1024+512*14)
    def test_small_complete_live_graph_below_declared_bound(self):
        a=f.cross_cancellation();c=p.construct(a,p.Budget(),model_sha='0'*64)
        self.assertLess(deep({'arrays':a,'certificate':c}),c['accounting']['estimated_owned_bytes'])
    def test_current_four_tree_boxes_and_sequences_reserve(self):
        boxes=[tuple((float(-i-1),float(i+1)) for i in range(62)) for _ in range(60)]
        seqs=[(F(2**2097-2*i,2**1074),F(-(2**2097-2*i),2**1074)) for i in range(1350)]
        self.assertLess(deep((boxes,seqs)),4*2**20)
if __name__=='__main__':unittest.main()
