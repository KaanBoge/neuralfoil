# Data Phase Report: first experimental extractions
Started 2026-08-22, last updated 2026-08-23 (Section 5 correction and pilot). Covers NASA TM-81927 (Harris), NACA WR L-143 (Ferri), NACA TN 3607 scouting.

## 1. The big correction first

Both Harris TM-81927 and Ferri WR L-143 were listed in the study documents as "tabulated". A page-by-page reconnaissance of the actual NTRS scans (contact sheets of all 141 Harris pages and all 171 Ferri pages) found NO force-coefficient tables in either. Both are plotted figures only. Every study document (paper outline, methods, proposal, handoff brief) has been corrected to say "plotted", and the digitization protocol now applies to all sources.

## 2. Harris TM-81927 Figure 8: the pilot dataset (DONE)

Figure 8 (page 58): cd vs M for the NACA 0012 at alpha = -0.14 deg, four series: Rn = 3, 6, 9 million with fixed transition, and 3 million free.

**Method (two independent passes, as the Methods require).** The page is scanned rotated and slightly skewed, so nothing was read against global pixel coordinates. Pass 1: a machine pass (PowerShell + C#) detected every heavy gridline (machine-measured pitch: 0.0025 in cd, 0.025 in M), verified the axis anchors against the printed labels, then traced dark ink runs row by row and clustered them into marker centroids and curve tracks. Pass 2: visual reading of high-zoom crops to identify marker shapes (circle, square, diamond, plus) and cross-check positions. Where the two passes overlap they agree to 2-4 drag counts.

**Results (47 points in harris-fig8.csv, with provenance, quality tiers, per-point uncertainties):**
- Free transition (plus, 3e6): plateau cd 0.0060-0.0063 from M 0.30 to 0.70, gentle rise from ~0.755, endpoint 0.0296 at M 0.84.
- Fixed 3e6 (circle): plateau 0.0090-0.0092, rise to 0.0311 at M 0.84.
- Fixed 6e6 (square): plateau 0.0079-0.0084, steepest late rise, crosses the others to the highest endpoint 0.0336 at M 0.84.
- Fixed 9e6 (diamond): elevated plateau ~0.0110 (trip overdrag), appears only above M ~0.5, ends near M 0.83 with no 0.84 endpoint.
- In the knee (M 0.76-0.80) the four printed curves overlap into one band; points there carry band-level uncertainty flags and looser series assignment. This is a property of the print, not of the extraction, and matches McCroskey's warning about scatter in this regime.

**Pre-registered sanity gate (run against the live NeuralFoil engine in the deployed Studio, raw path, NACA 0012, alpha -0.14):**
| Series | Experiment | NeuralFoil | Error | Verdict |
|---|---|---|---|---|
| fixed 3e6 (xtr 0.05) | 0.0090 | 0.00897 | 0.3 counts | PASS |
| fixed 6e6 (xtr 0.05) | 0.0080 | 0.00794 | 0.6 counts | PASS |
| fixed 9e6 (xtr 0.05) | 0.0110 | 0.00742 | 36 counts | FAIL, as the trip-drag caveat predicts. Series demoted one quality tier; note recorded. |
| free 3e6 | 0.0063 | 0.00512 at n_crit 9 | 12 counts | resolved by n_crit sweep |

The n_crit sweep (Methods Step 3) puts the free-transition point at effective n_crit ~ 4.5 (cd 0.00644 at n_crit 4, 0.00614 at 5). That becomes the convention-table entry for the 8-ft TPT: free transition maps to n_crit ~ 4.5, and with it the gate passes within 2 counts.

## 3. Ferri WR L-143: pilot curve extracted, gate verdict important

Structure discovered: each airfoil gets a three-page set (CL vs M; CD vs M by alpha; Cm vs M at fixed CL). Pilot: NACA 2309, Figure 33 Cont. (page 81). [SUPERSEDED, kept for the audit trail: the first manual read reported 16 diamond-curve points with plateau 0.0121-0.0126 and endpoint 0.0778 at M 0.943. The Section 5 QC re-read replaced these: the plateau read had a 5-8 count glyph-top bias and the "0.0778 endpoint" was the neighboring alpha=1 square glyph. Current corrected values: plateau 0.0115-0.0121, diamond endpoint 0.0742 at M 0.941; ferri-2309.csv now holds the corrected three-sweep set. Use Section 5, not this paragraph, for numbers.]

**Conventions read from the report text (2026-08-23, agent pass with page citations).** The 24-airfoil tests were made in the Guidonia (Italy) 1.31 x 1.74 ft open-jet high-speed tunnel, NOT the Langley 24-inch tunnel; chords 1.575 in (t/c >= 8%) and 1.969 in (thinner); Reynolds number held approximately CONSTANT at 0.34-0.42 million across M 0.40-0.94 by varying tunnel density (the study documents' "3.4-4.2 million" was a factor-of-ten error, now corrected everywhere); lift is true C_L from a three-component balance (not cn), drag from the same balance (no wake rake); models polished steel with no transition devices (free transition implied); open jet, so no choking, with quoted validity to M 0.94 for these chords; figure scheme confirmed (Figures 23-46, three sheets per airfoil, 2309 = Figure 33; the 24-airfoil order is documented).

**Gate verdict: FAIL on absolute cd, usable for increments.** Re-run at the TRUE Reynolds number (0.34/0.38/0.42 million, n_crit 4/6/9): NeuralFoil predicts cd 0.0062-0.0072 for the 2309 at alpha 0 vs the measured 0.0116, a gap of 44-54 counts at every plausible setting. The verdict below therefore stands at documented conditions. NeuralFoil predicts cd 0.0046-0.0079 for the 2309 at plausible tunnel Re (0.7-2 million) even at n_crit 4; experiment reads 0.0124. A ~50-count offset cannot be explained by transition settings alone; 1945 24-inch-tunnel data carries low-Re, high-turbulence, and interference effects, which is why McCroskey grades this era low. Disposition per the pre-registered design: WR L-143 is used for the drag-rise INCREMENT (Step 8 fits Delta-CD relative to each source's own subcritical baseline, which subtracts per-tunnel offsets), not for absolute CD levels. Also still needed from the report text: the actual Re-vs-M operating curve and the cn-vs-cl convention.

## 4. NACA TN 3607: scouted, ready for the mentor list

75 pages. Text and tables pp 1-25 (p25: ordinates table), apparatus pp 26-28, calibration figures pp 29-35, airfoil family profiles p36, per-airfoil and per-group data plots pp 37-70 (three-panel and six-panel cl/cd/cm vs M layouts; summary figures around pp 58-70), schlieren plates pp 71-75. Next step per the frozen Methods: read the figure captions, propose the 35-40 curve list, get mentor approval, then digitize with the pipeline above.

## 5. Update 2026-08-23: QC correction and the recalibration pilot

**QC correction (Ferri).** A three-agent workflow re-read Figure 33 with label-anchored programmatic calibration. It caught two errors in the first manual diamond read: a 5-8 count systematic bias (glyph tops read instead of centers) and a curve mix-up above M 0.78 where the manual trace slid onto the neighboring alpha = 1 square curve (the reported "diamond endpoint 0.078" was the square's; the true diamond endpoint is 0.0742 at M 0.941). ferri-2309.csv is fully replaced with the corrected three-sweep set (alpha = -1/0, 1, 2; 45 rows). The double-read rule exists precisely for this.

**Onset validation.** The three sweeps' measured drag-rise onsets order and place themselves exactly as Eq. 8 predicts: M_crit = 0.630 (alpha 2), 0.664 (alpha 1), 0.692 (alpha 0/-1), computed from the live engine's suction peaks; Karman-Tsien numeric agrees within 0.003.

**Recalibration pilot (calibration data only; Harris never loaded). NUMBERS BELOW ARE THE CORRECTED PINNED-PATH VERSIONS (2026-08-23, second pass).** Fitting target: drag-rise increment DeltaCD above each sweep's own subcritical baseline, M <= 0.90, scipy least_squares with soft_l1 loss per the frozen Methods, run in the pinned Python environment (neuralfoil 0.3.3, aerosandbox 4.2.10, WSL Python 3.14.4).

IMPORTANT CORRECTION found while moving to the pinned path: the shipped pipeline is NOT a pure quartic. Reading the installed aerosandbox source (kulfan_airfoil.py) shows CD_wave = 80(M - mach_crit)^4 only between mach_crit and mach_dd (= mach_crit + 0.068); beyond drag divergence it blends into a separate RANS-tuned term (slope-50 form). The first pilot pass compared against the pure quartic extrapolated everywhere, which overstated stock's error (574 counts). The honest comparator is the exact shipped pipeline evaluated by aerosandbox itself.

FINAL results, third pass at the TRUE tunnel Reynolds number (0.38 million, constant; see the Ferri conventions read below). MAE on the held-out sweep, drag counts:
- Exact stock pipeline (ASB 4.2.10): 154.7 / 303.1 / 314.9, mean 257.6.
- Null k*80(M-Mc)^4: per-fold 77.8 / 43.2 / 79.1, mean 66.7; full-fit k = 0.122 (effective constant 9.8 vs the shipped 80; the legacy constant 20 is far closer than 80).
- Selected F1: DeltaCD = 1.314*(M-Mc)^2.607: per-fold 58.3 / 32.9 / 57.8, mean 49.7. Beats the null on every fold; cuts exact-stock error by 81 percent out-of-sample.
- No-harm: zero added drag below mach_crit (structural); onset-window MAE stock vs refit: 10.5 vs 10.0, 5.1 vs 4.4, 18.7 vs 18.1 counts (refit better on all three sweeps).
- mach_crit from the exact ASB formula at Re 0.38e6: 0.6871 / 0.6542 / 0.6246 (alpha 0 / 1 / 2); the app's Eq. 8 implementation agrees within 0.005, and the measured onset ordering matches these predictions exactly.
(Second-pass numbers at the previously assumed Re 1e6, kept for the audit trail: stock 231.2, null 77.7, F1 55.2 with A=1.076 b=2.44.)
- Engine parity: the six 0012 sanity-gate cases reproduce EXACTLY (all five decimals) between the browser port and the pinned Python path, as do the 2309 CL/CD/Cp_min values. The Step 7-style equivalence concern for the subsonic network is closed; the transonic-layer standalone reproduction (Step 7 proper) still awaits Phase B.

This pilot demonstrates the Phase B machinery end to end on the pinned path. It is not the paper's fit; the binding selection happens only in the full leave-one-source-out fit per the pre-registration (see docs/protocol-deviations.md D2).
- F1o (onset offset) fit its offset to exactly 0 and was dropped by parsimony.

**No-harm check:** the refit term is structurally zero below M_crit, so every subcritical prediction (including the 0.3 and 0.6 count Harris gate passes) is unchanged to the last bit; in the onset window [Mc, Mc+0.05] MAE improves slightly (11.9 to 10.8 counts).

**Scope honesty:** one airfoil, one source, free transition, low Re; cross-validation spans angle of attack, not airfoils. This pilot demonstrates the Phase B machinery and the direction and rough size of the correction; the paper's constants come from the full pre-registered fit (TN 3607 + Ferri set, quality weights, family holdouts, one-shot Harris/TN 1546 scoring).

## 6. Files
- data/harris-fig8.csv (47 rows) and data/ferri-2309.csv (45 rows, corrected 2026-08-23): master-CSV format with provenance columns.
- Extraction imagery: h58-*.jpg (Harris), f81-*.jpg (Ferri), tn-sheet*.jpg (TN 3607 contact sheets).
- Tools: harness.html (pdf.js renderer + headless save), plotscan.ps1 / rowband.ps1 / trace.ps1 / cluster.ps1 / paths.ps1 (gridline detection, run tracing, marker clustering).
- The local render server on :8153 is a session task; it stops when this session ends.
