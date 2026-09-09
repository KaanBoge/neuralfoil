"""Add verified original-convention Kulfan features to transition inputs."""
from pathlib import Path
import numpy as np
import transition_inputs as transition

ROOT = Path(__file__).resolve().parent


def _merge(name, d):
    with np.load(ROOT / "shape_inputs" / f"{name}.npz", allow_pickle=False) as archive:
        assert np.array_equal(archive["row_id"], np.arange(len(d["BASE_CD"])))
        if name == "historical":
            assert np.array_equal(archive["nf2_row_id"], d["nf2_row_id"])
        assert np.array_equal(archive["alpha"], d["alpha"])
        assert np.array_equal(archive["Re"], d["Re"])
        d["K18"] = archive["K18"].copy()
    assert d["K18"].shape == (len(d["BASE_CD"]), 18)
    assert np.isfinite(d["K18"]).all()
    d["X42"] = np.column_stack([d["X24"], d["K18"]])
    d["X62"] = np.column_stack([d["X44"], d["K18"]])
    return d


def load_historical():
    return _merge("historical", transition.load_historical())


def load_exposed(name):
    return _merge(name, transition.load_exposed(name))
