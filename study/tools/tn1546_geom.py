"""Exact TN 1546 16-series geometries from Table II (scan p.18), built by the
report's own rules: thickness = 16-009 ordinates scaled by (t/c)/9, applied
PERPENDICULAR to the mean line; mean line = the cli=1.0 ordinates and slopes
scaled by the section's design lift; LE radius 0.3966((t/c)/9)^2.

Cross-source check: the 16-009 thickness column here is digit-identical to the
independent printing in TN 3607 Table I at every shared station, which verifies
both transcriptions at once."""
import numpy as np

# Table II, transcribed 2026-08-28. station, t_ordinate(16-009), meanline_ord(cli=1), meanline_slope(cli=1)
TAB = [
    (0.0,   0.0,   0.0,   0.62234),
    (0.6,   0.676, 0.295, 0.40665),
    (1.25,  0.969, 0.535, 0.34771),
    (2.5,   1.354, 0.930, 0.29155),
    (5.0,   1.882, 1.580, 0.23432),
    (7.5,   2.274, 2.120, 0.19993),
    (10.0,  2.593, 2.587, 0.17486),
    (15.0,  3.101, 3.364, 0.13804),
    (20.0,  3.498, 3.982, 0.11032),
    (25.0,  3.812, 4.475, 0.08743),
    (30.0,  4.063, 4.861, 0.06743),
    (40.0,  4.391, 5.356, 0.03227),
    (50.0,  4.500, 5.516, 0.0),
    (60.0,  4.376, 5.356, -0.03227),
    (70.0,  3.952, 4.861, -0.06743),
    (80.0,  3.149, 3.982, -0.11032),
    (90.0,  1.888, 2.587, -0.17486),
    (95.0,  1.061, 1.580, -0.23432),
    (100.0, 0.090, 0.0,  -0.62234),
]

def build(tc_pct, cli, n=100):
    x0 = np.array([r[0] for r in TAB]) / 100
    yt0 = np.array([r[1] for r in TAB]) / 100 * (tc_pct / 9.0)
    yc0 = np.array([r[2] for r in TAB]) / 100 * cli
    dy0 = np.array([r[3] for r in TAB]) * cli
    xc = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n)))
    yt = np.interp(xc, x0, yt0)
    yc = np.interp(xc, x0, yc0)
    dy = np.interp(xc, x0, dy0)
    th = np.arctan(dy)
    up = np.column_stack([xc - yt*np.sin(th), yc + yt*np.cos(th)])[::-1]
    lo = np.column_stack([xc + yt*np.sin(th), yc - yt*np.cos(th)])[1:]
    return np.vstack([up, lo])

SECTIONS = {
    '16-009': (9, 0.0), '16-109': (9, 0.1), '16-209': (9, 0.2), '16-509': (9, 0.5),
    '16-306': (6, 0.3), '16-309': (9, 0.3), '16-312': (12, 0.3), '16-315': (15, 0.3),
}
GEOM = {k: build(t, c) for k, (t, c) in SECTIONS.items()}
np.save('tn1546_geom.npy', GEOM, allow_pickle=True)

print("TN 1546 holdout geometries (exact, from published Table II):")
for k, g in GEOM.items():
    x, y = g[:, 0], g[:, 1]
    n2 = len(g) // 2
    xi = np.linspace(0.001, 0.999, 400)
    yu = np.interp(xi, x[:n2+1][::-1], y[:n2+1][::-1])
    yl = np.interp(xi, x[n2:], y[n2:])
    t = (yu - yl).max() * 100
    cam = ((yu + yl) / 2).max() * 100
    print(f"  {k}: t/c {t:6.3f}%  camber {cam:6.3f}%  (design {SECTIONS[k][0]}%, cli {SECTIONS[k][1]})")
