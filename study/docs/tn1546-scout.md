# TN 1546 (Family Holdout): Structure Scout

Prepared 2026-08-23. Structure only: per the one-shot rule extended by amendment A10, no data values were read, and full digitization must complete and freeze BEFORE the final Phase B fit is selected.

## What the scan holds

50 pages. Text pp. 3-16 (conditions, precision, 16-series geometry equations, discussion); Table I p. 17 = airfoil-to-figure index (rotated, low contrast); Table II p. 18 = 16-009 ordinates. Data: Fig 1 (p. 19) wake-survey vs force-test cd comparison (the only marker-per-point figure); Fig 2 (p. 20) corrected-vs-uncorrected wall data for 16-309; Figure 3(a)-(x), pp. 21-44: THE core block, one airfoil per page, rotated 90 degrees: cl vs M, cd vs M (one faired curve per alpha, line-style coded, NO point markers), and cm strips with individually offset scales; Figure 4(a)-(f), pp. 45-50: constant-M cross plots at M 0.30-0.775.

CRITICAL: the NTRS scan TRUNCATES after Figure 4. Figures 5-20 (l/d, critical-Mach, force-break summaries listed in the report's own Table I) are absent. Any plan expecting them from this file fails; if needed, a second scan source must be located.

## The 24 airfoils (reconstructed from Table I; endpoints verified on-page)

16-009; 16-106, 16-109, 16-115, 16-130; 16-209, 16-215; 16-306, 16-309, 16-312, 16-315, 16-321; 16-409; 16-506, 16-509, 16-512, 16-515, 16-521, 16-530; 16-709, 16-712, 16-715; 16-1009, 16-1012. Verified: Fig 3(a) = 16-009, Fig 3(x) = 16-1012. Thickness 6-30 percent, design lift 0-1.0: a wide, genuinely independent family grid.

## Conditions

Langley 24-inch high-speed tunnel; duralumin models, 5-inch chord, end plates with leakage corrections (revised vs Rep 763); M 0.3 to ~0.8; Re approximately 0.85-2.0e6 varying with M; free transition implied (smooth models, no trips mentioned); data UNCORRECTED for wall constriction (~2 percent in M at supercritical speeds; Fig 2 quantifies it for one airfoil); near-choking data omitted; quoted accidental errors cl +/-0.005, cd +/-0.0005, cm +/-0.002, alpha +/-0.1 deg. Angles of attack are NON-INTEGER (2-degree spacing offset by -0.23: e.g. -6.23 ... 5.77, cambered to 11.77).

## Digitization risk register (drives the extraction plan)

1. Every Fig 3 page rotated 90 degrees (pipeline handles this; Harris was also rotated).
2. NO markers: faired curves only, so points are curve samples; per-alpha curves END at different Mach (never extrapolate past an endpoint).
3. Alpha identity rides on 5-7 similar dash patterns: the highest-risk judgment; mitigation: trace from the legend anchor and verify at multiple Mach stations; independent-reader QC quota raised for this source.
4. cm strips have per-strip offset zeros (out of scope anyway: moment is excluded).
5. Wall-constriction correction (~2 percent in M) must be handled per the convention table BEFORE comparisons; Fig 2 gives the report's own corrected example to calibrate the adjustment.
6. Choking arrows on the zero-lift axis mark theoretical choking M: points near them get exclusion flags per Step 3.

## Plan consequence

TN 1546 digitization is scheduled after TN 3607 calibration extraction and before final model selection (A10). Its own convention table (cn/cl: this report plots cl directly; wall-correction rule; per-alpha endpoints) gets written first, then the gate, then extraction with raised QC.
