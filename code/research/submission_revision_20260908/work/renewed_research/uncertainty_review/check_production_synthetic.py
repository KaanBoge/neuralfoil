"""Independent synthetic production comparison; no study data or producer run."""
from pathlib import Path
from fractions import Fraction as F
import hashlib
import importlib.util
import json
import random
import numpy as np
import math_checks as exact

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'measurement_sensitivity/sensitivity.py'


def main():
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    spec=importlib.util.spec_from_file_location('reviewed_sensitivity',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.PROJECT==HERE.parents[3]
    rng=random.Random(67339); comparisons=0; largest=0.
    for _ in range(160):
        rows=[tuple(F(rng.randrange(0,65),64) for _ in range(3)) for _ in range(5)]
        weights=[F(i,15) for i in range(1,6)]
        y,b,c=map(lambda a:np.asarray(a,dtype=float),zip(*rows))
        w=np.asarray(weights,dtype=float)
        for r in [F(0),F(9,100),F(1)]:
            for eps in [F(0),F(1,10000),F(3,10),F(2)]:
                observed=[module.RowBox(b,c,y,w,float(r)).bounds(float(eps)),
                          module.ShiftCurve(b,c,y,w,float(r)).bounds(float(eps))]
                expected=[exact.box_bounds(rows,weights,eps,r),
                          exact.common_shift_bounds(rows,weights,eps,r)]
                for a,e in zip(observed,expected):
                    error=float(np.max(np.abs(np.asarray(a,dtype=float)-np.asarray(e,dtype=float))))
                    largest=max(largest,error)
                    if error>1e-13:raise AssertionError((a,e,error))
                    comparisons+=1
    for cls,args in [(module.RowBox,()),(module.SharedShifts,(['g'],))]:
        obj=cls([0.],[1.],[1.],[1.],.09,*args)
        radius=module.first_zero(obj,.09)
        root=float(F(91,191))
        assert radius['radius_lower_CD']<=root<=radius['radius_upper_CD']
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest
    record=dict(status='PASS',comparison_pairs=comparisons,max_absolute_difference=largest,
                source_sha256=digest,new_fits=0,empirical_labels_read=False,
                longdouble_precision=int(np.finfo(np.longdouble).precision))
    (HERE/'PRODUCTION_SYNTHETIC_QA.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))


if __name__=='__main__':main()
