import numpy as np
import aerosandbox as asb

def naca4(m, p, t, n=80):
    x = 0.5 * (1 + np.cos(np.pi * np.arange(n + 1) / n))
    yt = t / 0.2 * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    if p > 0:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x**2))
        dy = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p)**2 * (p - x))
    else:
        yc = np.zeros_like(x); dy = np.zeros_like(x)
    th = np.arctan(dy)
    up = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])
    lo = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])[::-1]
    return np.vstack([up, lo[1:]])

af = asb.Airfoil(name="naca2309", coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()

# the pilot's Mach points per sweep (from the corrected dataset, M <= 0.94)
sweeps = {
    0: [0.40, 0.50, 0.60, 0.65, 0.70, 0.72, 0.75, 0.78, 0.80, 0.822, 0.845, 0.869, 0.897],
    1: [0.40, 0.501, 0.601, 0.65, 0.70, 0.75, 0.78, 0.80, 0.82, 0.848, 0.87, 0.898],
    2: [0.40, 0.50, 0.60, 0.65, 0.70, 0.72, 0.75, 0.765, 0.78, 0.80, 0.82, 0.85, 0.87, 0.899],
}
for a, Ms in sweeps.items():
    out = af.get_aero_from_neuralfoil(alpha=a, Re=1e6, mach=0.30, model_size="xlarge", n_crit=9)
    cd_base = np.asarray(out["CD"]).item()
    mc = np.asarray(out["mach_crit"]).item()
    mdd = np.asarray(out["mach_dd"]).item()
    print(f"alpha {a}: mach_crit={mc:.4f} mach_dd={mdd:.4f} CD(M0.3)={cd_base:.5f}")
    for M in Ms:
        o = af.get_aero_from_neuralfoil(alpha=a, Re=1e6, mach=M, model_size="xlarge", n_crit=9)
        cd = np.asarray(o["CD"]).item()
        print(f"  M={M:.3f} CD={cd:.5f} dCD_vs_M0.3={(cd-cd_base)*1e4:.1f}cts")
