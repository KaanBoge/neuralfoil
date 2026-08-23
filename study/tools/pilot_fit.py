import numpy as np
import aerosandbox as asb
from scipy.optimize import least_squares

def naca4(m, p, t, n=80):
    x = 0.5 * (1 + np.cos(np.pi * np.arange(n + 1) / n))
    yt = t / 0.2 * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x**2)) if p > 0 else np.zeros_like(x)
    dy = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p)**2 * (p - x)) if p > 0 else np.zeros_like(x)
    th = np.arctan(dy)
    up = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])
    lo = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])[::-1]
    return np.vstack([up, lo[1:]])

af = asb.Airfoil(name="naca2309", coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()

# corrected extracted sweeps (M, CD): QC dataset, points M <= 0.90 used for fit/score per frozen Step 5
SW = {
    0: [(0.40,0.0116),(0.50,0.0116),(0.60,0.0115),(0.65,0.0121),(0.70,0.0120),(0.72,0.0136),(0.75,0.0158),(0.78,0.0170),(0.80,0.0185),(0.822,0.0232),(0.845,0.0296),(0.869,0.0342),(0.897,0.0485)],
    1: [(0.40,0.0141),(0.501,0.0140),(0.601,0.0140),(0.65,0.0139),(0.70,0.0149),(0.75,0.0169),(0.78,0.0191),(0.80,0.0209),(0.82,0.0242),(0.848,0.0330),(0.87,0.0364),(0.898,0.0539)],
    2: [(0.40,0.0179),(0.50,0.0175),(0.60,0.0178),(0.65,0.0196),(0.70,0.0220),(0.72,0.0239),(0.75,0.0250),(0.765,0.0249),(0.78,0.0260),(0.80,0.0263),(0.82,0.0300),(0.85,0.0401),(0.87,0.0461),(0.899,0.0639)],
}

sweeps = []
for a, pts in SW.items():
    o = af.get_aero_from_neuralfoil(alpha=a, Re=0.38e6, mach=0.30, model_size="xlarge", n_crit=9)
    mc = np.asarray(o["mach_crit"]).item()
    Ms = np.array([p[0] for p in pts]); CDs = np.array([p[1] for p in pts])
    base_mask = Ms <= mc - 0.03
    base = CDs[base_mask].mean()
    tr_mask = (Ms > mc) & (Ms <= 0.90)
    # exact stock pipeline delta at the transonic points
    stock = []
    for M in Ms[tr_mask]:
        oo = af.get_aero_from_neuralfoil(alpha=a, Re=0.38e6, mach=float(M), model_size="xlarge", n_crit=9)
        stock.append(np.asarray(oo["CD"]).item() - np.asarray(o["CD"]).item())
    sweeps.append(dict(a=a, mc=mc, base=base, M=Ms[tr_mask], d=CDs[tr_mask] - base, stock=np.array(stock)))
    print(f"alpha {a}: mach_crit={mc:.4f} baseline={base:.5f} nTr={tr_mask.sum()}")

S = 0.001
def model(form, p, M, mc):
    x = np.maximum(0, M - mc)
    if form == "null": return p[0] * 80 * x**4
    return p[0] * np.maximum(1e-12, x) ** p[1]

def fit(form, train):
    def resid(p):
        r = []
        for s in train:
            r.append((model(form, p, s["M"], s["mc"]) - s["d"]) / S)
        return np.concatenate(r)
    x0 = [0.13] if form == "null" else [1.0, 2.4]
    bounds = ([1e-4], [10]) if form == "null" else ([1e-4, 0.5], [500, 6])
    r = least_squares(resid, x0, loss="soft_l1", bounds=bounds)
    return r.x

def mae(form, p, s): return np.mean(np.abs(model(form, p, s["M"], s["mc"]) - s["d"])) * 1e4
def mae_stock(s): return np.mean(np.abs(s["stock"] - s["d"])) * 1e4

print("\n== exact stock pipeline (ASB 4.2.10) MAE per sweep ==")
sm = [mae_stock(s) for s in sweeps]
print("  ", [f"a{s['a']}: {m:.1f}" for s, m in zip(sweeps, sm)], f"mean {np.mean(sm):.1f}")

print("\n== LOSO (scipy soft_l1, pinned path) ==")
for form in ["null", "F1"]:
    ho = []
    for i in range(3):
        train = [s for j, s in enumerate(sweeps) if j != i]
        p = fit(form, train)
        ho.append(mae(form, p, sweeps[i]))
        print(f"  {form} fold{i} (holdout a{sweeps[i]['a']}): params {np.round(p,4)} heldMAE {ho[-1]:.1f}")
    print(f"  {form} mean held-out MAE: {np.mean(ho):.1f} counts")

pfull = fit("F1", sweeps)
print(f"\nfull-fit F1 params: A={pfull[0]:.4f} b={pfull[1]:.4f}")
pnull = fit("null", sweeps)
print(f"full-fit null k: {pnull[0]:.4f} (effective constant {80*pnull[0]:.1f})")
# no-harm: model at subcritical = 0 by construction (max(0, M-mc)); onset window MAE
for s in sweeps:
    w = s["M"] <= s["mc"] + 0.05
    if w.sum():
        st = np.mean(np.abs(s["stock"][w] - s["d"][w])) * 1e4
        rf = np.mean(np.abs(model("F1", pfull, s["M"][w], s["mc"]) - s["d"][w])) * 1e4
        print(f"onset window a{s['a']}: stock {st:.1f} refit {rf:.1f} counts")
