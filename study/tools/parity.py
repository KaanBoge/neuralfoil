import numpy as np, neuralfoil as nf, inspect

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

c0012 = naca4(0, 0, 0.12)
print("== NACA 0012 alpha -0.14, xlarge ==")
cases = [("free3e6_n9", 3e6, 9, 1, 1), ("fixed3e6", 3e6, 9, 0.05, 0.05), ("fixed6e6", 6e6, 9, 0.05, 0.05),
         ("fixed9e6", 9e6, 9, 0.05, 0.05), ("free3e6_n4", 3e6, 4, 1, 1), ("free3e6_n5", 3e6, 5, 1, 1)]
for name, Re, nc, xu, xl in cases:
    r = nf.get_aero_from_coordinates(c0012, alpha=-0.14, Re=Re, model_size="xlarge", n_crit=nc, xtr_upper=xu, xtr_lower=xl)
    print(f"{name}: CL={np.asarray(r['CL']).item():.4f} CD={np.asarray(r['CD']).item():.5f}")

print("== NACA 2309 Re 1e6 free n9 ==")
c2309 = naca4(0.02, 0.3, 0.09)
for a in [-1, 0, 1, 2]:
    r = nf.get_aero_from_coordinates(c2309, alpha=a, Re=1e6, model_size="xlarge", n_crit=9, xtr_upper=1, xtr_lower=1)
    uekeys = [k for k in r.keys() if "ue" in k.lower()]
    if a == -1:
        print("ue-like keys sample:", uekeys[:4], "... total", len(uekeys))
    ue = np.concatenate([np.asarray(r[k]).ravel() for k in uekeys])
    cpmin = float(np.min(1 - ue**2))
    print(f"alpha {a}: CL={np.asarray(r['CL']).item():.4f} CD={np.asarray(r['CD']).item():.5f} Cpmin={cpmin:.4f}")

print("== ASB kulfan_airfoil transonic lines ==")
import aerosandbox.geometry.airfoil.kulfan_airfoil as ka
for i, line in enumerate(inspect.getsource(ka).splitlines()):
    l = line.strip()
    if any(k in l for k in ("mach_crit", "mach_dd", "CD_wave", "Cp_min", "0.6582", "1.011", "critical_mach")):
        print(f"{i}: {l[:160]}")
