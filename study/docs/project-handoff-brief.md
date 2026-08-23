# Project Handoff Brief: NeuralFoil Trustworthiness Study

**Purpose of this document.** A complete, self-contained state-of-the-project briefing for any writing assistant (human or AI) helping draft the research paper. Everything below is locked fact or completed work. Last updated August 23, 2026.

---

## Instructions for the writing assistant (read first)

1. **Every fact you need is in this brief and the three companion documents.** Do not invent, estimate, or "recall" any number, citation, formula, or result not stated here. If something is missing, ask the author; do not fill the gap.
2. **The pre-registered study battery has not run yet.** The Phase A battery, the full calibration fit, the one-shot holdout scoring, and the Phase C confidence calibration have NOT happened, so there are no Results, no Discussion of findings, no Conclusion. Do not fabricate outcomes of any of them. What DOES exist (see Section 8): pilot data extractions from Harris and Ferri with QC, executed sanity gates, and a machinery-validation pilot fit on calibration data only; these may be described in Methods as protocol validation, never presented as the study's findings. The Introduction, Literature Review, and Methods are written and polished; treat them as near-final text to refine, not to replace.
3. **Style rules (non-negotiable):** never use em dashes (the — character) or double hyphens; use commas, colons, or separate sentences instead. American spelling. APA citations. The program's journal density is about 500 words per page. Plain, precise, honest voice: claims are measured, never conferred; limitations are stated, never hidden.
4. **Honesty framing used throughout:** trustworthiness is *measured and bounded*, not proven. The paper repairs what can be repaired and bounds what cannot. Avoid the words "guarantee," "prove," and "certify."

---

## 1. Project identity

- **Author:** Kaan, high-school student, Lumiere research program (mentored, ~12 to 20 page final paper, example journal: Oxford JSS).
- **Working title:** *From Black Box to Bounded Tool: An Experimental Audit, Recalibration, and Uncertainty Calibration of the NeuralFoil Aerodynamic Surrogate*
- **Research question:** Where does NeuralFoil disagree with wind-tunnel experiment; can its weakest layer, the transonic drag rise, be recalibrated to reduce error on data it has never seen; and can its self-reported confidence be turned into calibrated error bounds?
- **Compact 20-word form:** "Where does NeuralFoil disagree with experiment, does recalibrating its transonic layer reduce held-out error, and is its confidence calibrated?"

## 2. The three-phase design

**Phase A, the audit (validity map).** NeuralFoil's predictions compared against published wind-tunnel data at matched Mach, Reynolds number, and transition state, at fixed lift coefficient. Deliverable: a validity-map figure (flow regimes against airfoil families, green/yellow/red cells, gray for no public data). Phase A is frozen as a complete, self-contained paper before any fitting begins.

**Phase B, the fix (recalibration).** The neural network stays frozen. Only the post-processing wave-drag formula is refit: three free parameters (leading coefficient, exponent, onset offset between predicted critical Mach and measured drag-rise onset). Fitting target is the drag-rise *increment*, never absolute CD. Robust least squares (soft-L1), leave-one-source-out cross-validation, mandatory one-parameter null model to beat. Pre-registered success criteria on the near holdout: at least 30% reduction in mean absolute error of the drag-rise increment versus the stock formula, and drag-divergence Mach (M_dd) error cut in half, both judged against the McCroskey scatter band. One-shot rule: holdout evaluated exactly once. No-harm check: subcritical predictions unchanged.

**Phase C, the safety (uncertainty calibration), NEW.** Reuses Phase A's comparison points; no new data. Audits the *stock* pipeline only. Regimes split at NeuralFoil's predicted M_crit. Calibration target, fixed in advance: within each of five equal-count confidence bins per regime, the empirical frequency of absolute drag error at or below T = 20 drag counts is compared with the bin's mean confidence score; reported metric is expected calibration error (count-weighted mean absolute gap). Conformal bound: the 90th percentile of absolute drag error over calibration-set points, per regime, stated as "with 90% coverage, drag error is within N counts." Coverage measured exactly once on holdout points, judged against the exact two-sided 95% binomial interval around 90% for that regime's point count. Either outcome (usable or uninformative) is reported. Structural prediction: the confidence score is blind above M_crit by construction, because the network never sees the Mach number.

## 3. What NeuralFoil is (locked facts)

- Sharpe & Hansman (2025), arXiv:2503.16323. Neural network trained on about 7.9 million XFOIL solutions. Inputs: airfoil shape (CST/Kulfan parameters), angle of attack, Reynolds number, n_crit, forced-transition locations. Mach number is NOT a network input.
- Compressibility is post-processing only: corrections to lift and moment; drag gets nothing below the critical Mach number. Above it, one empirical formula adds wave drag: CD_wave = 80(M − M_crit)⁴ in the current analysis path (AeroSandbox's kulfan_airfoil.py, get_aero_from_neuralfoil). A legacy generate_polars() path carries different constants and is never the reference.
- M_crit comes from a symbolic-regression surrogate applied to the predicted incompressible minimum pressure coefficient (Eq. 8 of the paper). Drag divergence at about M_crit + 0.068.
- The authors' own words: the drag-rise formula "typically errs on the side of over-estimating wave drag"; onset predictions are "reasonably trustworthy," wave-drag magnitude beyond is not.
- Outputs: CL, CD, CM, Top_Xtr, Bot_Xtr, analysis_confidence, plus 32-station boundary-layer quantities per surface. About 30x faster than XFOIL single-case, up to 1,000x in batches; always returns an answer.
- Prior transonic work, both simulation-only: the author's own CFD-based retune (AeroSandbox 4.2.4 changelog, never written up) and KHRONOS (Sarker, Batley, Sarojini, & Saha, 2025, arXiv:2512.10287), a multi-fidelity surrogate that *uses* NeuralFoil as a low-fidelity source and targets flow fields; it does not correct NeuralFoil's formulas. No published work has audited NeuralFoil against wind-tunnel data.

## 4. Data sources and their locked roles

| Source | Role |
|---|---|
| NACA TN 3607 (Daley & Dick, 1956) | Calibration (4-digit family, thickness and camber varied, to M 1.0, plotted) |
| NACA WR L-143 (Ferri, 1945) | Calibration (24 airfoils, M 0.40 to 0.94, plotted per-airfoil figures; the NTRS scan has no force tables) |
| NACA TN 1546 (Lindsey et al., 1948) | Family holdout (16-series, 24 airfoils, withheld entirely) |
| NASA TM-81927 (Harris, 1981) | Same-family, independent-facility check (NACA 0012, plotted figures; the NTRS scan has no force tables; excluded from fitting) |
| NASA TP-2890 (SC(2)-0714) and AGARD AR-138 (RAE 2822) | Boundary-of-validity probes, pre-registered as NOT expected to transfer |
| NACA TM 1240 (Göthert, 1949) | Independent-facility cross-check (DVL tunnel) |
| NACA TN 1813 (Nitzberg & Crandall, 1949) | Drag-rise mechanism reference |
| NASA TM-100019 (McCroskey, 1987) | Quality tiers and experimental noise floor (40+ tunnels, NACA 0012) |
| NACA TR-824 (Abbott et al., 1945) | Subsonic baseline reference; its critical-Mach charts are theory-only consistency checks |

Method guards already fixed in the Methods: per-source convention tables (cn vs cl, transition state, Mach corrections), a sanity gate (one subcritical point must match within 10 drag counts and 0.05 CL before bulk extraction), digitization capped at ~35 to 40 curves with 10% double-digitized to quantify extraction error, M_dd extracted by cubic-polynomial fit (backup rule: +20 counts above the subcritical plateau), effective sample size reported as curves and sources, never raw points.

## 5. The three finished documents (paste-ready)

1. **paper-outline-FINAL.md**: complete Introduction and six-part Literature Review, about 3,700 words, four figures and two tables specified, full APA references. Contributions list (four): validity map; confidence audit extended into calibrated bounds; first experimental calibration of the drag-rise layer with quantified held-out error; released machine-readable dataset (supporting contribution).
2. **methods-section.md**: ten-step recipe, about 1,750 words, with the complete pre-registration box covering Phases B and C.
3. **proposal-updated-answers.md**: all six program-proposal answers under the new question.

All three were updated to the umbrella question on August 22 and passed a two-auditor adversarial review (fact fidelity plus mentor-style coherence); all findings were fixed.

## 6. NeuralFoil Studio, the companion app (built, verified, live)

**URL:** https://kaanboge.github.io/neuralfoil-studio.html (single self-contained 3.2 MB HTML file, runs offline, no install; source in the kaanboge.github.io repository with full commit history).

**The headline capability:** the actual NeuralFoil 0.3.3 network (the exact nn-xlarge weight tensors, MIT license) runs live in the page. Selecting any airfoil computes its complete run (141 angles x 6 Reynolds numbers) in about 150 ms. The port re-implements the full pipeline: airfoil normalization, CST least-squares fit, the swish MLP, the Mahalanobis confidence penalty, and the flipped-evaluation symmetry average, matching NeuralFoil's own get_aero_from_airfoil path.

**Verification numbers to cite (all reproducible in-page via buttons on the Checks tab):**
- Ported network vs the 846-case AG04 reference run: max differences CL 0.0029, CD 0.55% worst-case, transition 0.0002, confidence 0.005. The residual is attributable to the five-decimal rounding of the stored reference coordinates (a jitter test at that rounding level moves CL by up to 0.0054).
- Hess-Smith panel solver vs the closed-form Joukowski exact solution: error falls monotonically with panel count (CL error 0.044 to 0.012 from 48 to 384 panels); the cusped trailing edge makes this a conservative test.
- Reality spot checks: E387 shows its documented mid-chord laminar separation bubble at Re 200k, reattaching at the predicted transition (0.563); S1223 gives CLmax 2.25 vs the published ~2.2; NACA 2412 gives CL 0.80 at 5 degrees and Re 200k, the published value.

**Full tab inventory (13 tabs):**
1. **Flow**: live 2D flow simulation; viscous mode matches the panel field to the run's surface velocities; Thwaites/Head integral boundary layer from the run's real edge velocities and transition points; wake sized to carry the run's real CD; separation marks and laminar-separation-bubble brackets; particles with sub-stepped advection that cannot tunnel through thin airfoils; streamlines; pressure-field view; hover probe; click-a-surface BL station readout with reconstructed velocity profile; per-airfoil "What you are seeing is..." description.
2. **3D view**: the 2D solution extruded into an orbitable wing with every Flow layer: pressure-colored surface (or material look), BL sheet, wake slab, stagnation/transition/separation span lines, stream surfaces tip to tip, pressure field as one continuous translucent volume (the exact extrusion of the 2D field), rounded tip fairings (geometry only), force vectors. Honest caption: no tip vortices or downwash simulated.
3. **Polars**: six charts across six Reynolds numbers, low-confidence shading, stall metrics, aerodynamic center, the clickable validity-map heatmap (confidence over the full 141 x 6 grid), CSV and full-run JSON export.
4. **Pressure & transition**: real Cp distributions, transition markers, inviscid overlay, Karman-Tsien Mach slider with sonic line and supersonic-pocket shading.
5. **Transonic lab**: critical-Mach and wave-drag charts with the study's three pre-registered sliders, experimental CSV overlay, the pre-registered soft-L1 three-parameter fit button (validated by synthetic round-trip: truth A=120, b=3.5, offset 0.01 recovered as 121/3.50/0.010), per-point residual dashboard, 400-resample bootstrap with 95% intervals and a curve envelope, M_dd markers.
6. **Model sizes**: fidelity-vs-speed comparison of all eight NeuralFoil sizes (real measured data).
7. **Geometry**: NACA 4-digit designer with exact equations, "analyze this design live" button, and the family study (sweeps thickness 6 to 24% or camber 0 to 6% through seven live runs; at Re 200k best L/D falls monotonically 69 to 53 with thickness).
8. **Compare**: two airfoils side by side, geometry stats (LE radius, TE angle), live inviscid polars, both airfoils' NeuralFoil runs overlaid.
9. **Flight lab**: section performance at real flight conditions (ISA atmosphere, chord/speed/altitude to Reynolds), labeled textbook finite-wing induced-drag estimate.
10. **Checks**: live audits of the active run against classical methods (Squire-Young drag closure, pressure-integration lift bookkeeping, Michel transition correlation), the Joukowski solver verification, and the ported-network verification button.
11. **Digitizer**: turns scanned wind-tunnel chart images into data: four-click affine axis calibration (rotation-tolerant; validated by exact round-trip on a synthetically rotated chart), magnifier, CSV export, one-click send into the Transonic lab. This is the tool for the study's digitization step.
12. **Movie maker**: records webm videos of four scenes including the supersonic-pocket Mach ramp.
13. **About**: full provenance and honesty statements for every computed quantity.

**Other app facts:** all 1,655 UIUC airfoils searchable (with t<8 / c>2 filters and hover shape previews); users can load their own .dat files (Selig or Lednicer) or drop them on the page; analysis-conditions panel exposes n_crit (4 to 14) and forced boundary-layer trips, real network inputs, recomputing the run live (validated: n_crit 6 moves AG04 transition 0.253 to 0.202; a trip at x/c 0.10 forces transition to 0.121); works on phones; exports render print-white.

**How the paper should use the app:** one Methods paragraph presenting it as the companion artifact plus reproducibility statement; figures for the paper are generated from its PNG exports; cite the in-page verification numbers above.

## 7. Python-side reproducibility

`gen_dataset.py` (in the same repository) reproduces any airfoil's dataset with the real Python NeuralFoil package, using the same raw path (`nf.get_aero_from_airfoil`) and grid as the app. Planned check: run two or three airfoils on independent hardware (the author's Mac) and state agreement in Methods. Pinned environment: Python 3.11+, neuralfoil 0.3.3, aerosandbox, scipy, pandas, matplotlib.

## 8. What is NOT done (do not write as if it were)

- Correction to earlier drafts: page-by-page reconnaissance of the NTRS scans found NO force-coefficient tables in Harris TM-81927 or Ferri WR L-143. Both are plotted figures only, so every source is digitized. All documents have been updated to say "plotted".
- DONE (2026-08-22): Harris TM-81927 Figure 8 (cd vs M, NACA 0012, alpha = -0.14 deg, four series: Rn 3/6/9 x 10^6 fixed transition plus 3 x 10^6 free) extracted as the pilot dataset: 47 points in `harris-fig8.csv` with provenance, quality tiers (A/B/C), per-point uncertainties, and a dual-method protocol (machine gridline-calibrated extraction cross-checked against visual marker reading; grid pitch 0.0025 in cd, 0.025 in M per heavy line, machine-verified). Findings: fixed-transition plateaus 0.0091 (3e6), 0.0081 (6e6), ~0.0110 (9e6, trip-overdrag contaminated, appears only above M~0.5), free 0.0062; series print-merge in the knee (M 0.76-0.80) so points there carry band-level uncertainty flags; series separate again above M 0.80 with the 6e6 square crossing to the highest endpoint (0.0336 at M 0.84).
- Sanity gate (pre-registered, Step 3) RUN against the live browser engine: fixed 3e6 passes at 0.3 counts error, fixed 6e6 at 0.6 counts, fixed 9e6 fails by 36 counts exactly as the trip-drag caveat predicts (documented, series demoted a quality tier), free transition matches at n_crit ~ 4.5 (effective tunnel turbulence mapping for the 8-ft TPT; convention-table entry recorded).
- PILOT ONLY (2026-08-23): the Ferri 2309 extraction was corrected by an independent QC re-read (first manual diamond read had a 5-8 count bias and slid onto the square curve above M 0.78; ferri-2309.csv now holds the corrected three sweeps at alpha -1/0, 1, 2). A pilot recalibration on those Ferri increments (Harris never loaded; one-shot holdout intact) selected DeltaCD = 1.07*(M - M_crit)^2.42 by leave-one-sweep-out, cutting held-out MAE from 574 counts (stock 80(M-Mc)^4) to 51, with zero change below M_crit and a slight onset-window improvement. The measured onset order also matched Eq. 8's M_crit order (0.630/0.664/0.692 for alpha 2/1/0). This demonstrates the Phase B machinery; it is NOT the paper's fit.
- No Phase A battery, no full pre-registered fit, no holdout touched, no confidence calibration measured. Therefore: no Results, no Discussion of findings, no Conclusion, no Abstract yet.
- Next concrete steps: extract the Ferri per-airfoil CL/CD-vs-M pairs with the same pipeline; scout TN 3607 with contact sheets and assemble the mentor-approved curve list before its full digitization.

## 9. Future-work ladder (for the Discussion section, framed as outlook, not promises)

1. Propose winning recalibrated constants upstream to AeroSandbox as a pull request.
2. A follow-up conformal-calibration study turning confidence into per-prediction error bars.
3. Delta-learning: train a small correction network on errors in regimes the validity map flags.
4. True Mach-aware retraining on RANS data (collaboration-scale; KHRONOS is adjacent prior art).
