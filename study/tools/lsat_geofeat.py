"""Geometry features per corpus entry, computed from the same coordinates the
NF runs used: max thickness and its position, max camber and its position,
leading-edge radius, trailing-edge wedge angle, trailing-edge thickness."""
import json, os
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))

def load_pts(path):
    pts = []
    for L in open(os.path.join(BASE, path), errors="replace").read().splitlines()[1:]:
        p = L.split()
        if len(p) >= 2:
            try:
                x, y = float(p[0]), float(p[1])
            except ValueError:
                continue
            if -0.5 <= x <= 1.5 and -0.6 <= y <= 0.6:
                pts.append([x, y])
    a = np.array(pts); a[:, 0] -= a[:, 0].min()
    return a / a[:, 0].max()

out = {}
for key, g in GEO.items():
    try:
        a = load_pts(g["path"])
        le = int(np.argmin(a[:, 0]))
        up, lo = a[:le + 1][::-1], a[le:]
        xg = np.linspace(0.01, 0.99, 99)
        yu = np.interp(xg, up[:, 0], up[:, 1])
        yl = np.interp(xg, lo[:, 0], lo[:, 1])
        t = yu - yl; c = (yu + yl) / 2
        it, ic = int(np.argmax(t)), int(np.argmax(np.abs(c)))
        nose = a[max(0, le - 4): le + 5]
        d = nose - a[le]
        r2 = d[:, 0]**2 + d[:, 1]**2
        with np.errstate(divide="ignore", invalid="ignore"):
            leR = float(np.nanmedian(r2[r2 > 1e-10] / (2 * np.abs(d[:, 0][r2 > 1e-10]) + 1e-12)))
        su = (up[-1, 1] - np.interp(0.95, up[:, 0], up[:, 1])) / 0.05
        sl = (lo[-1, 1] - np.interp(0.95, lo[:, 0], lo[:, 1])) / 0.05
        teA = float(np.degrees(np.arctan(su) - np.arctan(sl)))
        out[key] = dict(camber=float(c[ic]), xcam=float(xg[ic]), xthick=float(xg[it]),
                        leR=min(leR, 0.1), teAng=teA,
                        teT=float(abs(up[-1, 1] - lo[-1, 1])))
    except Exception as e:
        print("geofeat FAIL", key, repr(e))
json.dump(out, open(os.path.join(BASE, "lsat-geofeat.json"), "w"), indent=0)
print(f"{len(out)} entries")
