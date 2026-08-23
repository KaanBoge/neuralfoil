# Frozen Quality-Tier Table and Noise Floor (from McCroskey, NASA TM-100019, 1987)

Extracted 2026-08-23 by page-cited reading of the actual report (23-page NTRS scan), per Methods Step 2 and amendment A11. This table is FROZEN as of its first commit: it is set before any fitting touches these weights and is never revised to favor a result.

## McCroskey's grouping scheme (his Tables 1-5, definitions on report pages 3-6)

- Group 1: experiments conducted with the utmost care, most nearly eliminating wind-tunnel error sources.
- Group 2: agree with BOTH Group-1 lift and drag correlations (within +/-0.0040 in beta*Cl_alpha and +/-0.0010 in Cd0).
- Group 3: agree in lift OR drag, not both.
- Group 4: satisfy basic criteria but with identified major problems, or fail them while covering ranges where qualitative information helps.
- Group 5: examined but not used.

## Frozen tier assignments for this study's sources

| Study source | McCroskey listing | Tier adopted here | Basis |
|---|---|---|---|
| Harris TM-81927 (8-ft TPT) | Group 2, first entry of Table 2 (p.18); "comparable in accuracy to Group 1"; conclusions call it "the most satisfactory single investigation of the conventional NACA airfoils to date," with a recommendation to correct side-wall boundary-layer interference before CFD validation use | Tier 1 (best available transonic force data), with the side-wall caveat carried into Limitations | Direct listing |
| Harris fixed-transition 9e6 series | Trip contamination discussed generally pp.4-6 (trips "increase Cd... difficult to quantify"; Vidal demoted for a large trip; Abbott LTPT trip "excessively thick") | Tier 2 (demoted one tier per deviation D5) | Direct trip-drag doctrine |
| Ferri WR L-143 (Guidonia open jet) | NOT LISTED anywhere in Tables 1-5; nearest analogues, the Langley 11-in and 24-in HST data of the same era, are both Group 5 | Tier 3, increment-only (per amendment A8); its Re 0.34-0.42e6 sits below McCroskey's fitted Re range entirely | Reasoned assignment, declared here |
| TN 3607 (Daley & Dick) | Not listed (not a 0012 test) | Tier 2 provisional pending its own convention table and gate | Reasoned assignment |
| TN 1546 (16-series, holdout) | Not listed; its facility (Langley 24-in HST) appears as Group 5 for a DIFFERENT 1949 dataset (Stack & Lindsey, Rep 922, "solid walls, variable AR") | Tier 3 provisional; wall-constriction ~2% in M uncorrected per its own text | Reasoned assignment |
| TR-824 (LTPT low speed) | LTPT tripped data noted for an "excessively thick trip" (Table 1 remark) | Tier 2 for untripped, Tier 3 for tripped | Direct remark |

## Frozen numeric noise floor (his numbers, with report pages)

- Untripped subcritical Cd0 (Groups 1-2, 1e6 < Re < 3e7): Eq. 2 fits to about +/-0.0003 (3 counts) (p.9, summary point 1). Group-1 point precision about +/-0.0002 (p.5).
- Tripped (fully turbulent) subcritical Cd0: about +/-0.0005 (5 counts) proposed (p.10, summary point 2).
- Drag-divergence Mach (NACA 0012): M_dd = 0.77 +/- 0.01, with drag creep above M 0.72 (p.8); maximum Cd0 0.11 +/- 10% between M 0.92 and 0.98 (p.10).
- Transonic drag scatter M 0.8-0.9: "virtually impossible to assess" (p.8): the regime's honesty ceiling.

## Transfer rule (per amendment A11)

McCroskey's bands are measured on the NACA 0012 only. This study applies them to non-0012 conventional sections as a FLOOR, widened by 50 percent (untripped 4.5 counts, tripped 7.5 counts) to acknowledge the extrapolation, and states this in Methods. Success criteria are judged against these widened bands.

## Study-relevant Reynolds caveat

McCroskey's correlations start at Re 1e6. Ferri (0.34-0.42e6) and parts of TN 1546 (0.85-2e6) sit at or below that edge; the low-Re transitional regime adds scatter his bands do not cover, one more reason Ferri is increment-only.
