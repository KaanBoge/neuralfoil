"""transonic_patch.py: the shipped NeuralFoil/AeroSandbox transonic drag layer,
reimplemented standalone per frozen Methods Step 7.

Consumes only: Cpmin_0 (incompressible minimum pressure coefficient), the
incompressible CD, t/c, and Mach. Returns mach_crit, mach_dd, CD_wave, and CD.
Faithfully transcribed from aerosandbox 4.2.10 kulfan_airfoil.py lines 445-547,
using the same numerics primitives (softmin, blend, cosine_hermite_patch) so the
reproduction is exact by construction. Before any constant is changed, this file
must reproduce the shipped pipeline to machine precision: run this module as a
script to execute that check.

The recalibration then swaps ONLY the quartic segment (the 80 and 4 constants,
via the `wave_constants` argument) while every other branch stays shipped.
"""
import numpy as np
import aerosandbox.numpy as anp
from aerosandbox.modeling.splines.hermite import cosine_hermite_patch

# Eq. 8 constants, exact from the shipped source
_C0 = 1.011571026701678
_C1 = 0.6582431351007195
_C2 = 0.6724789439840343
_C3 = -0.5504677038358711
MACH_DD_OFFSET = (0.1 / 320) ** (1 / 3)   # 0.067860...


def mach_crit_of(Cpmin_0):
    c = anp.softmin(Cpmin_0, 0, softness=0.001)
    return (_C0 - c + _C1 * (-c) ** _C2) ** _C3


def cd_wave(mach, Cpmin_0, t_over_c, wave_constants=(80.0, 4.0)):
    """The shipped wave-drag term. wave_constants=(A, b) parameterizes ONLY the
    pre-divergence quartic segment as A*(M - mach_crit)**b; (80, 4) is stock.
    The patch endpoint f_a stays continuous with the chosen segment."""
    A, b = wave_constants
    mach = np.asarray(mach, dtype=float)
    mach_crit = mach_crit_of(Cpmin_0)
    mach_dd = mach_crit + MACH_DD_OFFSET
    seg_end = A * MACH_DD_OFFSET ** b          # value at mach_dd from the chosen segment
    return np.where(
        mach < mach_crit,
        0.0,
        np.where(
            mach < mach_dd,
            A * (mach - mach_crit) ** b,
            np.where(
                mach < 1.1,
                cosine_hermite_patch(
                    mach,
                    x_a=mach_dd, x_b=1.1,
                    f_a=seg_end, f_b=0.8 * t_over_c,
                    dfdx_a=0.1, dfdx_b=-0.8 * t_over_c * 8,
                ),
                anp.blend(
                    8 * 2 * (mach - 1.1) / (1.2 - 0.8),
                    0.8 * 0.8 * t_over_c,
                    1.2 * 0.8 * t_over_c,
                ),
            ),
        ),
    )


def cd_total(mach, Cpmin_0, CD_incompressible, t_over_c, wave_constants=(80.0, 4.0)):
    """Shipped pipeline drag: incompressible CD (which the shipped code does NOT
    beta-correct) plus the wave term."""
    return np.asarray(CD_incompressible, dtype=float) + cd_wave(mach, Cpmin_0, t_over_c, wave_constants)


if __name__ == '__main__':
    # ---- Step 7 machine-precision check against the real pipeline ----
    import aerosandbox as asb

    GEOM = np.load('tn3607_geom.npy', allow_pickle=True).item()
    machs = np.round(np.arange(0.30, 1.1001, 0.01), 4)
    worst = 0.0
    worst_case = None
    n = 0
    for sec in ['64A004', '64A006', '64A009', '64A012', '64A206', '64A506']:
        af = asb.Airfoil(name=sec, coordinates=GEOM[sec]).to_kulfan_airfoil()
        toc = af.max_thickness()
        for alpha in [0.0, 2.0, 4.0]:
            for Re in [0.68e6, 1.22e6, 1.58e6]:
                # incompressible reference (mach=0) gives Cpmin_0 and CD_incomp
                o0 = af.get_aero_from_neuralfoil(alpha=alpha, Re=Re, mach=0.0,
                                                 model_size="xlarge", n_crit=6)
                cp0 = float(np.asarray(o0["Cpmin_0"]).item()) if "Cpmin_0" in o0 else None
                if cp0 is None:
                    # fall back: mach_crit is reported; invert not needed, use reported directly
                    raise SystemExit("Cpmin_0 not exposed; adjust key")
                cd0 = float(np.asarray(o0["CD"]).item())
                for M in machs:
                    o = af.get_aero_from_neuralfoil(alpha=alpha, Re=Re, mach=float(M),
                                                   model_size="xlarge", n_crit=6)
                    cd_ship = float(np.asarray(o["CD"]).item())
                    cd_mine = float(cd_total(M, cp0, cd0, toc))
                    d = abs(cd_ship - cd_mine)
                    n += 1
                    if d > worst:
                        worst, worst_case = d, (sec, alpha, Re, M, cd_ship, cd_mine)
    print(f"cases compared: {n}")
    print(f"worst |CD_shipped - CD_patch|: {worst:.3e}")
    if worst_case:
        s, a, r, m, cs, cm = worst_case
        print(f"  at {s} alpha {a} Re {r:.2e} M {m}: shipped {cs:.10f} vs patch {cm:.10f}")
    print("machine precision" if worst < 1e-12 else
          ("acceptable (float-noise level)" if worst < 1e-9 else "REPRODUCTION FAILURE: investigate"))
