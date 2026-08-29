"""Reference vectors for the in-page port self-test of NeuralFoil B.
Fixed Kulfan parameters (NACA 2412 fit by aerosandbox itself), a handful of
conditions spanning subsonic, transonic and post-onset, all 8 sizes."""
import json
import numpy as np
import aerosandbox as asb

af = asb.Airfoil("naca2412").to_kulfan_airfoil()
kp = af.kulfan_parameters
SIZES = ["xxsmall","xsmall","small","medium","large","xlarge","xxlarge","xxxlarge"]
CONDS = [
    dict(alpha=3.0,  Re=1e6,   mach=0.0,  n_crit=9.0, xtr_upper=1.0, xtr_lower=1.0),
    dict(alpha=-2.0, Re=3.8e5, mach=0.45, n_crit=6.0, xtr_upper=1.0, xtr_lower=1.0),
    dict(alpha=5.0,  Re=3e6,   mach=0.72, n_crit=9.0, xtr_upper=0.05, xtr_lower=0.05),
    dict(alpha=1.0,  Re=2e6,   mach=0.85, n_crit=6.0, xtr_upper=1.0, xtr_lower=1.0),
    dict(alpha=12.0, Re=2e5,   mach=0.1,  n_crit=9.0, xtr_upper=1.0, xtr_lower=1.0),
]
out = {"kp": {"upper": list(map(float, kp["upper_weights"])),
              "lower": list(map(float, kp["lower_weights"])),
              "le": float(kp["leading_edge_weight"]),
              "te": float(kp["TE_thickness"])},
       "t_over_c": float(af.max_thickness()),
       "conds": CONDS, "results": []}
for c in CONDS:
    row = {}
    for s in SIZES:
        o = af.get_aero_from_neuralfoil(model_size=s, **c)
        row[s] = {k: float(np.asarray(o[k]).item())
                  for k in ("CL","CD","CM","analysis_confidence","mach_crit")}
    out["results"].append(row)
json.dump(out, open("nfb-ref.json", "w"), indent=1)
print("wrote nfb-ref.json,", len(CONDS), "conditions x 8 sizes")
