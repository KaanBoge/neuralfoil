import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
import develop_v2 as v


class Cycle2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = v.load_data()

    def test_feature_schema(self):
        self.assertEqual(self.d["X24"].shape,(8371,24))
        self.assertEqual(len(set(self.d["group"])),93)
        np.testing.assert_array_equal(self.d["X24"][:,:16],self.d["X16"])
        self.assertTrue(np.isfinite(self.d["X24"]).all())

    def test_bounds_and_zero_strength(self):
        base = np.array([.01,.02,.03])
        for kind in ["log","relative","additive"]:
            np.testing.assert_allclose(v.correct(kind,np.array([-1e5,0,1e5]),base,1),[.005,.02,.06])
            np.testing.assert_allclose(v.correct(kind,np.array([-1e5,0,1e5]),base,0),base)

    def test_rich_features_do_not_use_measured_coefficients(self):
        changed={key:value.copy() for key,value in self.d.items()}
        changed["MEAS_CD"][:]=999
        changed["MEAS_CL"][:]=-999
        changed["yCD"][:]=888
        np.testing.assert_array_equal(v.add_features(changed)["X24"],self.d["X24"])

    def test_weighted_relative_objective_constant(self):
        base=np.array([.01,.02,.03,.04]); meas=np.array([.001,.018,.09,.06]); weights=np.array([1.,2.,3.,4.])
        truth=(meas-base)/base
        constants=[]
        for prediction in [np.full(4,-.4),np.zeros(4),np.full(4,.7)]:
            cd_loss=np.sum(weights*np.abs(base*(1+prediction)-meas))
            surrogate=np.sum(weights*base*np.abs(prediction-np.clip(truth,-.5,1)))
            constants.append(cd_loss-surrogate)
        np.testing.assert_allclose(constants,constants[0],atol=1e-14)

    def test_portable_classic_and_hist(self):
        idx=np.arange(400)
        d={k:a[idx] for k,a in self.d.items() if a.ndim and len(a)==8371}
        specs=[("gb16_log",GradientBoostingRegressor(loss="absolute_error",n_estimators=5,max_depth=2,random_state=824)),
               ("hist24_relative",HistGradientBoostingRegressor(loss="absolute_error",max_iter=5,min_samples_leaf=10,early_stopping=False,categorical_features=None,random_state=824))]
        for family,model in specs:
            x=d[v.feature_key(family)]; kind=v.target_kind(family)
            target=d["yCD"] if kind=="log" else (d["MEAS_CD"]-d["BASE_CD"])/d["BASE_CD"]
            model.fit(x,target)
            with tempfile.TemporaryDirectory(prefix="neuralfoil-v2-parity-") as directory:
                parity=v.export((family,1.),model,d,Path(directory))
                self.assertLess(parity["max_absolute_CD_difference"],1e-12)
                artifact=json.loads((Path(directory)/"candidate.json").read_text())
                self.assertEqual(len(artifact["feature_names"]),x.shape[1])


if __name__=="__main__":unittest.main()
