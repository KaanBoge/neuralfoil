#!/usr/bin/env python3
"""
gen_dataset.py: generate a full NeuralFoil dataset for any airfoil and build a
complete NeuralFoil Studio page for it.

This is the bridge between the Studio app and the study pipeline: run it on a
machine with Python + neuralfoil + aerosandbox installed (your Mac), and any
airfoil gains the full viscous treatment in Studio: real polars, pressure
distributions, transition, confidence, the data-matched flow field, boundary
layer, and wake.

Usage examples
--------------
  python gen_dataset.py --dat ag12.dat --name AG12 \
      --template neuralfoil-studio.html --out ag12-studio.html

  python gen_dataset.py --uiuc e387 --template neuralfoil-studio.html --out e387-studio.html

  python gen_dataset.py --dat naca2412.dat --json-only --out naca2412-dataset.json

Requirements: pip install neuralfoil aerosandbox numpy
(matches the study's pinned environment; see the paper's Methods)

The dataset grid is fixed to match Studio exactly:
  alphas: -15 to +20 in 0.25 deg steps (141 points)
  Re:     50k, 100k, 200k, 500k, 1M, 5M
  Cp:     from boundary-layer edge velocity, Cp = 1 - (ue/V)^2, at the
          boundary-layer stations NeuralFoil reports
"""

import argparse, json, re, sys, time, urllib.request

import numpy as np
import aerosandbox as asb
import neuralfoil as nf

ALPHAS = [round(-15 + 0.25 * i, 2) for i in range(141)]
RE_LIST = ["50000", "100000", "200000", "500000", "1000000", "5000000"]
MODEL = "xlarge"
MODEL_SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]

# IMPORTANT: use neuralfoil's own get_aero_from_airfoil (the raw network path).
# This matches the AG04 reference dataset and the Studio's in-page ported network
# exactly. Do NOT use asb.Airfoil.get_aero_from_neuralfoil, which additionally
# applies AeroSandbox's post-stall blending and compressibility factors.
N_BL = len(nf.bl_x_points)


def load_airfoil(args):
    if args.uiuc:
        url = f"https://m-selig.ae.illinois.edu/ads/coord_seligFmt/{args.uiuc}.dat"
        print(f"downloading {url}")
        text = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", "replace")
        lines = text.strip().splitlines()
        name = args.name or lines[0].strip()
        pts = []
        for ln in lines[1:]:
            parts = ln.split()
            if len(parts) >= 2:
                try:
                    x, y = float(parts[0]), float(parts[1])
                    if abs(x) < 10 and abs(y) < 10:
                        pts.append([x, y])
                except ValueError:
                    pass
        coords = np.array(pts)
    else:
        raw = open(args.dat).read().strip().splitlines()
        name = args.name or raw[0].strip()
        pts = []
        for ln in raw[1:]:
            parts = ln.split()
            if len(parts) >= 2:
                try:
                    pts.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
        coords = np.array(pts)
    if len(coords) < 25:
        sys.exit("airfoil has too few points")
    return name, coords


def scalar(v):
    a = np.asarray(v).flatten()
    return float(a[0])


def vector(v):
    return [round(float(x), 4) for x in np.asarray(v).flatten()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", help="Selig-format .dat file")
    ap.add_argument("--uiuc", help="UIUC file id, e.g. e387 (downloads coordinates)")
    ap.add_argument("--name", help="display name (default: first line of the file)")
    ap.add_argument("--template", help="existing neuralfoil-studio.html to rebuild around this dataset")
    ap.add_argument("--out", required=True, help="output file (.html with --template, else .json)")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args()
    if not args.dat and not args.uiuc:
        sys.exit("need --dat or --uiuc")

    name, coords = load_airfoil(args)
    af = asb.Airfoil(name=name, coordinates=coords)
    print(f"airfoil: {name}  ({len(coords)} points)")

    # probe one run to confirm the key names of this neuralfoil version
    probe = nf.get_aero_from_airfoil(airfoil=af, alpha=5.0, Re=2e5, model_size=MODEL)
    needed = ["CL", "CD", "CM", "Top_Xtr", "Bot_Xtr", "analysis_confidence", "upper_bl_ue/vinf_0", "lower_bl_ue/vinf_0"]
    missing = [k for k in needed if k not in probe]
    if missing:
        print("available keys:", sorted(probe.keys()))
        sys.exit(f"keys not found in this neuralfoil version: {missing}")
    bl_x = [round(float(x), 5) for x in nf.bl_x_points]
    print(f"boundary-layer stations: {N_BL} (uniform midpoints, from nf.bl_x_points)")

    results = {}
    t0 = time.time()
    for re_s in RE_LIST:
        Re = float(re_s)
        out = {"CL": [], "CD": [], "CM": [], "Top_Xtr": [], "Bot_Xtr": [],
               "confidence": [], "cp_upper": [], "cp_lower": []}
        for a in ALPHAS:
            r = nf.get_aero_from_airfoil(airfoil=af, alpha=a, Re=Re, model_size=MODEL)
            out["CL"].append(round(scalar(r["CL"]), 4))
            out["CD"].append(round(scalar(r["CD"]), 6))
            out["CM"].append(round(scalar(r["CM"]), 4))
            out["Top_Xtr"].append(round(scalar(r["Top_Xtr"]), 4))
            out["Bot_Xtr"].append(round(scalar(r["Bot_Xtr"]), 4))
            out["confidence"].append(round(scalar(r["analysis_confidence"]), 4))
            ue_u = [scalar(r[f"upper_bl_ue/vinf_{i}"]) for i in range(N_BL)]
            ue_l = [scalar(r[f"lower_bl_ue/vinf_{i}"]) for i in range(N_BL)]
            out["cp_upper"].append([round(float(1 - u * u), 4) for u in ue_u])
            out["cp_lower"].append([round(float(1 - u * u), 4) for u in ue_l])
        results[re_s] = out
        print(f"  Re {re_s}: done ({time.time() - t0:.1f}s elapsed)")

    print("model-size comparison at Re 500k...")
    model_comparison = {}
    for ms in MODEL_SIZES:
        cl, cd = [], []
        t1 = time.time()
        for a in ALPHAS:
            r = nf.get_aero_from_airfoil(airfoil=af, alpha=a, Re=5e5, model_size=ms)
            cl.append(round(scalar(r["CL"]), 4))
            cd.append(round(scalar(r["CD"]), 6))
        dt = time.time() - t1
        model_comparison[ms] = {"CL": cl, "CD": cd,
                                "evals_per_second": int(len(ALPHAS) / max(dt, 1e-6))}
        print(f"  {ms}: {model_comparison[ms]['evals_per_second']} evals/s")

    t_single = time.time()
    nf.get_aero_from_airfoil(airfoil=af, alpha=5.0, Re=2e5, model_size=MODEL)
    single_ms = round((time.time() - t_single) * 1000, 2)

    data = {
        "airfoil_name": name,
        "coordinates": [[round(float(x), 5), round(float(y), 5)] for x, y in coords],
        "alphas": ALPHAS,
        "Re_list": RE_LIST,
        "bl_x_points": bl_x,
        "results": results,
        "model_comparison": model_comparison,
        "timing": {"single_eval_ms_xlarge": single_ms, "batch_size": 1,
                   "machine": "generated by gen_dataset.py"},
        "provenance": f"NeuralFoil, model_size={MODEL} unless noted, generated "
                      + time.strftime("%Y-%m-%d") + f" for {name} by gen_dataset.py",
    }
    blob = json.dumps(data, separators=(",", ": "))

    if args.template and not args.json_only:
        html = open(args.template, encoding="utf-8").read()
        new_html, n = re.subn(r"const NF = \{.*?\};\n", "const NF = " + blob + ";\n",
                              html, count=1, flags=re.S)
        if n != 1:
            sys.exit("could not find the dataset blob in the template")
        open(args.out, "w", encoding="utf-8").write(new_html)
        print(f"wrote {args.out}: a complete Studio for {name} "
              f"(open it or publish it next to the original)")
    else:
        open(args.out, "w", encoding="utf-8").write(blob)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
