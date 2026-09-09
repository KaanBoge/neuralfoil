"""Standalone standard-library synthetic witness generation; no project imports."""
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import time
import unittest


def main():
    root=Path(__file__).resolve().parent
    output=root/'SYNTHETIC_WITNESS.json'
    if output.exists():raise FileExistsError(output)
    stream=io.StringIO();start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_oracle'))
    value={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,
           'elapsed_seconds':time.perf_counter()-start,'python':sys.version,'platform':platform.platform(),
           'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in
                            ('PLAN_AND_PROOF.md','oracle.py','test_oracle.py','verify_synthetic.py')},
           'transcript':stream.getvalue(),'real_feature_or_model_arrays_read':False,
           'other_contractor_source_imported':False,'scope':'closed finite binary64 boxes, numeric equality including signed zero'}
    with output.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    print(stream.getvalue())
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
