"""Optional input convention; literal score_external formulas and quantization.

Copied numerical formulas from model_development_20260906/score_external.py
predict_base; only Airfoil-to-Kulfan conversion changes. No measured inputs.
Source and implementation SHA256 values are recorded by generate_inputs.py.
"""
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]/"model_development_20260906/reproduction"))
from reproduce_doubleclean import foil_stats2, SIZES
from tie_safe_normalization import to_kulfan_tie_safe


def predict_base(coordinates, alpha, re):
    import aerosandbox as asb
    foil = to_kulfan_tie_safe(asb.Airfoil(name="external_evaluation", coordinates=coordinates))
    outputs = {size: foil.get_aero_from_neuralfoil(alpha=np.asarray(alpha), Re=np.asarray(re), mach=0.0, n_crit=9, model_size=size) for size in SIZES}
    quant = lambda values, digits: np.array([float(f"{float(v):.{digits}f}") for v in np.atleast_1d(values)])
    cds = np.column_stack([quant(outputs[s]["CD"],6) for s in SIZES])
    cls = np.column_stack([quant(outputs[s]["CL"],5) for s in SIZES])
    cms = np.column_stack([np.atleast_1d(outputs[s]["CM"]) for s in SIZES])
    xl = outputs["xlarge"]
    top, bot = quant(xl["Top_Xtr"],4), quant(xl["Bot_Xtr"],4)
    conf, cm8 = quant(xl["analysis_confidence"],4), quant(cms.mean(axis=1),5)
    stat = foil_stats2(coordinates.tolist())
    cd8, cl8 = cds.mean(axis=1), cls.mean(axis=1)
    spread = np.maximum(np.percentile(cds,90,axis=1)-np.percentile(cds,10,axis=1),1e-6)
    n = len(alpha)
    fill = lambda key: np.full(n,stat[key])
    x9 = np.column_stack([alpha,np.log10(re),fill("t"),fill("c"),np.log(cd8),cl8,np.log(spread),top,bot])
    x16 = np.column_stack([alpha,np.log10(re),fill("t"),fill("tx"),fill("c"),fill("cx"),fill("leR"),fill("teA"),
                          np.log(cd8),cl8,np.log(spread),conf,top,bot,np.log(cds[:,0])-np.log(cds[:,7]),cm8])
    assert np.isfinite(x9).all() and np.isfinite(x16).all() and (cd8>0).all()
    return {"X9":x9,"X16":x16,"BASE_CD":cd8,"XLARGE_CD":cds[:,5],"all_CD":cds,"all_CL":cls,"stat":stat}


def rich(values):
    """Literal develop_v2.add_features arithmetic, with the same feature order."""
    d = {"X9": values["X9"], "X16": values["X16"], "BASE_CD": values["BASE_CD"],
         "XLARGE_CD": values["XLARGE_CD"], "all_model_CD": values["all_CD"], "all_model_CL": values["all_CL"]}
    x = d["X16"]
    cd, cl = d["all_model_CD"], d["all_model_CL"]
    extra = np.column_stack([np.abs(x[:,0]),x[:,9]**2,np.minimum(x[:,12],x[:,13]),np.maximum(x[:,12],x[:,13]),
        x[:,12]-x[:,13],(np.percentile(cd,90,axis=1)-np.percentile(cd,10,axis=1))/d["BASE_CD"],
        np.median(cd,axis=1)/d["BASE_CD"]-1,np.std(cl,axis=1)])
    d["X24"] = np.column_stack([x,extra])
    assert np.isfinite(d["X24"]).all()
    return d
