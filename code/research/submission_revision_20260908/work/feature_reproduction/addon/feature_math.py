"""Literal frozen feature operations extracted without project-specific imports.
Original source provenance is recorded in the addon manifest.
"""

import numpy as np

SIZES = ["xxsmall","xsmall","small","medium","large","xlarge","xxlarge","xxxlarge"]

GRID = [5,7,9,11,13]

FIELDS = {"CD":6,"CL":5,"confidence":4,"Top_Xtr":4,"Bot_Xtr":4}

def load_pts(text):
    out = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            try:
                x, y = float(fields[0]), float(fields[1])
            except ValueError:
                continue
            if -0.5 <= x <= 1.5 and -0.6 <= y <= 0.6:
                out.append([x, y])
    a = np.array(out)
    a[:, 0] -= a[:, 0].min()
    return a / a[:, 0].max()

def foil_stats2(points):
    """Literal numerical operations from recovered geometry descriptor code."""
    le = int(np.argmin([p[0] for p in points]))
    up, lo = points[:le + 1], points[le:]
    def interp(seg, x):
        for k in range(len(seg) - 1):
            a, b = seg[k], seg[k + 1]
            if (x-a[0])*(x-b[0]) <= 0 and abs(b[0]-a[0]) > 1e-9:
                return a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        return 0.0
    t = tx = c = cx = 0.0
    for k in range(1, 100):
        x = 0.5*(1-np.cos(np.pi*k/100))
        yu, yl = interp(up, x), interp(lo, x)
        th, cm = yu-yl, (yu+yl)/2
        if th > t:
            t, tx = th, x
        if abs(cm) > abs(c):
            c, cx = cm, x
    A = points[max(0, le-1)]
    B = points[le]
    Cp = points[min(len(points)-1, le+1)]
    a2 = np.hypot(B[0]-Cp[0], B[1]-Cp[1])
    b3 = np.hypot(A[0]-Cp[0], A[1]-Cp[1])
    c3 = np.hypot(A[0]-B[0], A[1]-B[1])
    s2 = (a2+b3+c3)/2
    tri = np.sqrt(max(1e-18, s2*(s2-a2)*(s2-b3)*(s2-c3)))
    leR = a2*b3*c3/(4*tri)
    v1 = [points[1][0]-points[0][0], points[1][1]-points[0][1]]
    v2 = [points[-2][0]-points[-1][0], points[-2][1]-points[-1][1]]
    den = np.hypot(*v1)*np.hypot(*v2) or 1e-9
    teA = np.degrees(np.arccos(np.clip((v1[0]*v2[0]+v1[1]*v2[1])/den, -1, 1)))
    return dict(t=t, tx=tx, c=c, cx=cx, leR=min(leR, 0.2), teA=teA)

def predict_base(coordinates, alpha, re):
    import aerosandbox as asb
    foil = asb.Airfoil(name="external_evaluation", coordinates=coordinates).to_kulfan_airfoil()
    outputs = {size: foil.get_aero_from_neuralfoil(alpha=np.asarray(alpha), Re=np.asarray(re), mach=0.0, n_crit=9, model_size=size) for size in SIZES}
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

def add_features(d):
    x = d["X16"]
    cd,cl = d["all_model_CD"],d["all_model_CL"]
    extra = np.column_stack([np.abs(x[:,0]),x[:,9]**2,np.minimum(x[:,12],x[:,13]),np.maximum(x[:,12],x[:,13]),
        x[:,12]-x[:,13],(np.percentile(cd,90,axis=1)-np.percentile(cd,10,axis=1))/d["BASE_CD"],
        np.median(cd,axis=1)/d["BASE_CD"]-1,np.std(cl,axis=1)])
    d["X24"] = np.column_stack([x,extra])
    assert np.isfinite(d["X24"]).all()
    return d

def calc(coordinates, alpha, reynolds):
    import aerosandbox as asb
    foil = asb.Airfoil(name="transition_sensitivity", coordinates=coordinates).to_kulfan_airfoil()
    matrices = {key: np.empty((len(alpha), len(GRID))) for key in FIELDS}
    for j, ncrit in enumerate(GRID):
        results = foil.get_aero_from_neuralfoil(alpha=alpha, Re=reynolds, mach=0., n_crit=ncrit,
                                               model_size="xlarge", xtr_upper=1., xtr_lower=1.)
        for key, digits in FIELDS.items():
            values = results["analysis_confidence" if key == "confidence" else key]
            matrices[key][:, j] = [float(f"{float(v):.{digits}f}") for v in np.atleast_1d(values)]
    assert all(np.isfinite(a).all() for a in matrices.values())
    assert (matrices["CD"] > 0).all()
    return matrices

def supplement(x24, matrices):
    extras = []
    for j in [0, 1, 3, 4]:
        extras += [np.log(matrices["CD"][:, j] / matrices["CD"][:, 2])]
        extras += [matrices[key][:, j] - matrices[key][:, 2] for key in ["CL", "confidence", "Top_Xtr", "Bot_Xtr"]]
    return np.column_stack([x24] + extras)
