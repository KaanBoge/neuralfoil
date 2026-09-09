"""Exclusive test evidence, including first failure source snapshots if needed."""
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import time
import unittest


def main():
    root=Path(__file__).resolve().parent;output=root/'TEST_ATTEMPT_2.json'
    if output.exists():raise FileExistsError(output)
    stream=io.StringIO();start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_producer'))
    names=('engine.py','domain.py','schema.py','runner.py','test_producer.py','verify_tests.py','verify_tests_2.py')
    record={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'seconds':time.perf_counter()-start,
            'transcript':stream.getvalue(),'python':sys.version,'platform':platform.platform(),'actual_model_arrays_opened':False,
            'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}}
    if not result.wasSuccessful():record['failed_source_snapshot']={n:(root/n).read_text() for n in names}
    with output.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print(stream.getvalue())
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
