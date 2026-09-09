"""Synthetic regression for consistency of the normalized-artifact parity check."""
import unittest
import numpy as np
import router_recovery1 as router

class RecoveryTests(unittest.TestCase):
    def test_raw_vs_normalized_operands(self):
        raw=np.array([[.5,.5+4e-12]])
        normalized=np.maximum(raw,0);normalized/=normalized.sum(axis=1,keepdims=True)
        design=np.array([[1000.,1500.]])
        artifact_prediction=np.sum(design*normalized,axis=1)
        with self.assertRaises(AssertionError):
            np.testing.assert_allclose(artifact_prediction,design@raw.ravel(),atol=1e-9,rtol=1e-12)
        np.testing.assert_allclose(artifact_prediction,design@normalized.ravel(),atol=1e-9,rtol=1e-12)
        self.assertLess(float(np.max(np.abs(design@raw.ravel()-design@normalized.ravel()))),2e-6)

if __name__=='__main__':unittest.main()
