# TN 3607: Figure Inventory and Proposed Mentor Curve List

Prepared 2026-08-23 from caption-level reading of all data pages (37-70). This is the proposal the frozen Methods Step 4 requires mentor approval on BEFORE full digitization of the primary calibration source. Total proposed: 37 curves, within the registered 35-40 cap.

## What the source actually is (corrected understanding)

Daley & Dick 1956. Ten airfoils, all reported as NORMAL-FORCE coefficient cn (convention-table consequence: cn-to-cl handling per Methods Step 3 applies to every TN 3607 comparison):
- Thickness series: 64A004, 64A006, 64A009, 64A012 (small duct)
- Camber series: 64A006, 64A206, 64A506 (small duct)
- Thickness-distribution series: 63A009, 64A009, 65A009, 16-009 (large duct)
Per-airfoil data: Figure 10(a)-(j), one page each (pp. 37-46): cn, cd, cm versus M at alpha from -4 to 12 deg depending on airfoil. Summary figures include Fig 17 (p. 60): drag-rise Mach M_dr vs cn for all three families, the report's own drag-divergence summary. Cross-plots (Figs 11, 14, 15, 19, 21) re-present the same data versus cn or alpha.

IMPORTANT registered constraint: the 16-009 belongs to the 16-series and is EXCLUDED from calibration by the pre-registration; its two curves below are extracted for the duct-systematic comparison and family-holdout context only, never entered into the calibration fit.

## Proposed curve list (priority order; drop from the bottom to shrink)

1. Fig 10(a) p37: 64A004 cd(M) at alpha 0, 2 [2 curves] - thinnest symmetric anchor.
2. Fig 10(d) p40: 64A006 cd(M) at alpha 0, 2 [2] - thickness step; shared camber-series baseline.
3. Fig 10(b) p38: 64A009 cd(M) at alpha 0, 2 [2] - thickness step; pivot to distribution series.
4. Fig 10(c) p39: 64A012 cd(M) at alpha 0, 2 [2] - steep end of the thickness exponent.
5. Fig 10(e) p41: 64A206 cd(M) at alpha -2, 0, 2 [3] - first camber step, brackets zero lift.
6. Fig 10(f) p42: 64A506 cd(M) at alpha 0, 2, 4 [3] - large camber step, straddles design lift.
7. Fig 17 p60: M_dr vs cn, all three panels [9 unique curves, 8-10 points each] - the authors' own drag-divergence fairing; cheap; cross-checks our M_dd extraction rule.
8. Fig 10(a-d): cd(M) at alpha 4 for the four symmetric sections [4] - lift dependence of drag rise.
9. Fig 10(g,i,j,h) pp43-46: cd(M) at alpha 0 (or -0.1) for 63A009, 65A009, 16-009*, 64A009-large-duct [4] - thickness-distribution family at fixed t/c; the 64A009 large-vs-small-duct pair quantifies the duct systematic. (*16-009: holdout-family context only.)
10. Same four at alpha 2 (or 1.9) [4] - include if budget remains (running total 33 through item 9).
11. Optional stretch: 64A206 at alpha 4, 64A506 at alpha 6 [2] - brings the total to 37 of the 40 cap; drop first.

## Why this shape

Priorities 1-6 give cd(M) sweeps at and near zero lift across both geometric axes the study fits (thickness, camber); priority 7 provides the dependent variable directly with the report's own fairing as a consistency check; 8-10 add the lift and thickness-distribution dimensions. Skipped: all cm figures (moment is out of scope per the frozen decision), the cn-vs-alpha and polar cross-plots (same data re-plotted; digitizing both would double-count), and the similarity-law correlation (Fig 23, derived quantities).

## Digitization notes for approval

Every caption on pp. 37-70 was legible; p. 45 is rotated landscape. Extraction will use the same machine gridline-calibrated pipeline as Harris Fig 8, with independent-reader QC on at least 10 percent of points (protocol amendment A9/D9), and the sanity gate must pass for this source before bulk extraction (Step 3, with amendment A8 if the absolute gate fails).
