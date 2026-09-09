"""Read verified, order-checked transition-sensitivity features; no writes."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "model_development_20260906_v2"))
import develop_v2 as v2


def load_historical():
    d = v2.load_data()
    with np.load(ROOT / "inputs/historical.npz", allow_pickle=False) as archive:
        assert np.array_equal(archive["nf2_row_id"], d["nf2_row_id"])
        assert np.array_equal(archive["X44"][:, :24], d["X24"])
        for key in ["X44", "ncrit_CD", "ncrit_CL", "ncrit_confidence", "ncrit_Top_Xtr", "ncrit_Bot_Xtr"]:
            d[key] = archive[key].copy()
    return d


def load_exposed(name):
    if name not in ["SG_exposed", "W_new_challenge"]:
        raise ValueError(name)
    prior = ROOT.parent / "model_development_20260907_search/exposed_inputs/forward_verified" / f"{name}.npz"
    with np.load(prior, allow_pickle=False) as archive:
        d = {key: archive[key].copy() for key in archive.files}
    with np.load(ROOT / "inputs" / f"{name}.npz", allow_pickle=False) as archive:
        assert np.array_equal(archive["X44"][:, :24], d["X24"])
        for key in ["X44", "ncrit_CD", "ncrit_CL", "ncrit_confidence", "ncrit_Top_Xtr", "ncrit_Bot_Xtr"]:
            d[key] = archive[key].copy()
    return d
