"""Read-only package integrity and membership tests; no model fitting."""
import unittest
import hashlib
from pathlib import Path
import numpy as np
import reproduce as r


class PackageTests(unittest.TestCase):
    def test_all_hashes_and_dtype_safety(self):
        m=r.read('manifest.json')
        for name,h in m['files'].items():
            self.assertEqual(hashlib.sha256((r.ROOT/name).read_bytes()).hexdigest(),h,name)
            if name.endswith('.npz'):
                with np.load(r.ROOT/name,allow_pickle=False) as z:
                    for k in z.files:self.assertNotEqual(z[k].dtype.kind,'O',(name,k))

    def test_memberships_and_dimensions(self):
        d=r.load('data/historical.npz');self.assertEqual(d['X62'].shape,(8371,62))
        self.assertEqual(len(set(d['group'])),93)
        for context in r.read('manifest.json')['contexts']:
            r.validate_membership(context,r.read('memberships/'+context+'.json'),d)

    def test_no_user_absolute_runtime_paths(self):
        for path in r.ROOT.glob('*.py'):
            self.assertNotIn('/'+'Users/',path.read_text(),path.name)


if __name__=='__main__':unittest.main()
