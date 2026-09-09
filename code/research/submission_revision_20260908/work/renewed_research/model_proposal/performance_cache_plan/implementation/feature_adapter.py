"""Narrow injected copies of the two frozen numerical helpers.
Source contract checked by tests; no data access, fitting or global patch on import.
"""
import numpy as np
from response_snapshot import ResponseSnapshot

def predict_base_with_foil(coordinates, alpha, re, foil, retained, math):
    SIZES=math.SIZES;foil_stats2=math.foil_stats2
    outputs = {size: retained.copy() if size=="xlarge" else foil.get_aero_from_neuralfoil(alpha=np.asarray(alpha), Re=np.asarray(re), mach=0.0, n_crit=9, model_size=size) for size in SIZES}
    # Literal historical formatting, then parse back to float.
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

def calc_with_foil(coordinates, alpha, reynolds, foil, math):
    GRID=math.GRID;FIELDS=math.FIELDS;retained=None
    matrices = {key: np.empty((len(alpha), len(GRID))) for key in FIELDS}
    for j, ncrit in enumerate(GRID):
        results = foil.get_aero_from_neuralfoil(alpha=alpha, Re=reynolds, mach=0., n_crit=ncrit,
                                               model_size="xlarge", xtr_upper=1., xtr_lower=1.)
        if ncrit==9:retained=ResponseSnapshot(results)
        for key, digits in FIELDS.items():
            values = results["analysis_confidence" if key == "confidence" else key]
            matrices[key][:, j] = [float(f"{float(v):.{digits}f}") for v in np.atleast_1d(values)]
    assert all(np.isfinite(a).all() for a in matrices.values())
    assert (matrices["CD"] > 0).all()
    if retained is None:raise ValueError("missing fixed ncrit9 response")
    return matrices,retained
