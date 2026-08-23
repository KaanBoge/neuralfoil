# Everything We Did: The Complete Record

NeuralFoil study, data phase and improvement pass, 2026-08-22 to 2026-08-23.
Repository: kaanboge.github.io/neuralfoil-study (commit history is the audit trail; the first study commit, 58e6877, is the public pre-registration timestamp).

## What this project is

The paper: "From Black Box to Bounded Tool: An Experimental Audit, Recalibration, and Uncertainty Calibration of the NeuralFoil Aerodynamic Surrogate." Three phases: A, map where NeuralFoil agrees and disagrees with historical wind-tunnel measurements; B, recalibrate its weakest layer, the transonic drag-rise formula, against calibration data and prove the improvement on holdout data it never saw; C, turn its confidence score into calibrated error bounds. The design is pre-registered: calibration sources (TN 3607, Ferri WR L-143) are fitted; holdouts (Harris TM-81927, the TN 1546 16-series family) are scored exactly once, at the end. The companion NeuralFoil Studio app (kaanboge.github.io/neuralfoil-studio.html) is feature-frozen and carries the exact ported network used for interactive checks.

## Day 1 (Aug 22): the data finally exists

1. Downloaded Harris TM-81927, Ferri WR L-143, and TN 3607 from NASA's NTRS archive (TN 3607 needed a 436-byte corruption fix).
2. Discovered by page-by-page reconnaissance that Harris and Ferri contain NO data tables in the public scans, only plotted figures, though our documents said "tabulated." Corrected every document.
3. Built an extraction pipeline from scratch, since this PC had no PDF tooling: a pdf.js render harness driven by headless Edge with a local save server, plus PowerShell/C# scripts that detect gridlines by darkness profiling, trace curve ink row by row, and cluster marker centroids. Axis calibration is machine-verified (Harris grid: 0.0025 in cd, 0.025 in M per line).
4. Extracted Harris Figure 8 (NACA 0012 drag vs Mach, alpha -0.14 deg, four series: Re 3/6/9 million fixed transition plus 3 million free): 47 points with provenance, per-point uncertainty, and quality tiers. Where the four printed curves merge (M 0.76-0.80) the points carry honest band flags.
5. Ran the pre-registered sanity gate against the engine: fixed 3e6 passed at 0.3 counts, fixed 6e6 at 0.6 counts, fixed 9e6 failed by 36 counts exactly as the literature's trip-drag warning predicts (series demoted a tier, with the physics as the reason), and free transition matched at an effective n_crit of about 4.5, which became the tunnel's convention-table entry.
6. Extracted a first Ferri curve (NACA 2309) and found the source ~50 counts high on absolute drag, so it entered the study as drag-rise increments only.

## Day 2 (Aug 23): making it more accurate without making anything worse

7. Extracted two more Ferri sweeps (alpha 1 and 2) with a three-agent workflow. The independent QC re-read caught two errors in the day-1 manual read: a 5-8 count bias (glyph tops read instead of centers) and a curve mix-up above M 0.78 (the manual trace had slid onto the neighboring curve). The dataset was replaced; the QC deltas on the new sweeps run 0-4 counts.
8. Ran the recalibration pilot on calibration data only, testing leave-one-sweep-out. Harris was never loaded into any fitting code, so the one-shot holdout stays intact.
9. Ran a four-lens audit (methods-consistency, statistics, journal-reviewer, data-pipeline) over every document and dataset: 46 findings. Then executed the fixes:
   - Durable storage plus public timestamp: the whole study now lives in the GitHub repository, and the commit history proves the design predates the fit.
   - A protocol deviations log (D1-D10) that declares every departure from the frozen Methods as a dated deviation instead of a silent patch, plus twelve pre-declared amendments (A1-A12: exact plateau estimator, complete M_dd rule, error aggregation unit, secondary comparators, uncertainty-aware weighting, conformal finite-sample form, coverage bootstrap, increment-mode gate, master schema, holdout extraction timing, numeric noise floor, extended n_crit range) awaiting mentor sign-off.
   - Pinned Python environment (WSL: neuralfoil 0.3.3, aerosandbox 4.2.10, scipy). Parity check: the browser port reproduces the pinned path EXACTLY, to all five decimals, on every gate case.
   - Reading the installed AeroSandbox source revealed the shipped pipeline is not a pure quartic: past drag divergence it switches to a gentler RANS-tuned blend. Our first stock-error figure (574 counts) had compared against the quartic extrapolated everywhere; all numbers were corrected to score against the exact shipped pipeline.
   - Reading Ferri's own text corrected our documents three ways: the tests ran in the GUIDONIA (Italy) open-jet tunnel, not Langley; chords are 1.575/1.969 inches; and Reynolds number was held approximately CONSTANT at 0.34-0.42 million at every Mach. The "3.4-4.2 million" in our table was a factor-of-ten slip. The gate re-run at the true Reynolds number still fails on absolute drag by 44-54 counts, so increment-only stands, now at documented conditions. Lift is true balance-measured CL, free transition, no choking, valid to M 0.94.
   - Downloaded and scouted the remaining sources: TN 1546 (the family holdout: 24 rotated pages of faired curves without markers, Re 0.85-2 million, scan truncates after Figure 4), McCroskey TM-100019, TR-824, TP-2890, TN 1813 (same 436-byte fix), TM 1240.
   - Froze the McCroskey quality-tier table with page citations: Harris is his Group 2 and "the most satisfactory single investigation of the conventional NACA airfoils to date"; Ferri is not listed at all (its era's analogues are his lowest group); the numeric noise floor is 3 counts untripped, 5 tripped, M_dd 0.77 plus or minus 0.01 for the 0012.
   - Read every TN 3607 data-page caption and wrote the 37-curve mentor proposal. Important truth found on the way: TN 3607's sections are the 6-series 64A family (reported as normal-force coefficient), not the 4-digit family our outline claimed, and it contains a 16-009 that the pre-registration correctly excludes to the holdout family. Consequence, corrected with dated notes: Harris is a conventional-section near holdout, not literally same-family.
   - Digitized the Ferri lift page (CL vs M for alpha -1, 0, 1, 2), populating the previously empty CL column. Bonus: the measured CL at alpha 0 (0.195) matches NeuralFoil within the gate's 0.05 CL criterion, so only drag carries the low-Re offset.
   - Built the single-read-path master dataset (92 rows, typed schema, sweep ids, numeric Reynolds, interpolated CL, split extraction tiers, double-read flags at 33.7 percent against the 10 percent quota) with its merge script.

## The numbers that matter (pilot, pinned Python path, true Reynolds number)

| Model | Held-out MAE (3 folds) | Mean |
|---|---|---|
| Exact stock pipeline (ASB 4.2.10) | 155 / 303 / 315 | 258 counts |
| Rescaled quartic, k about 0.12 (effective constant 10, not 80) | 78 / 43 / 79 | 67 counts |
| Selected: DeltaCD = 1.31 (M - M_crit)^2.61 | 58 / 33 / 58 | 50 counts |

An 81 percent out-of-sample error cut, winning every fold, with the no-harm rule verified: zero added drag below M_crit (the two 0.3/0.6-count gate passes are untouched), and the onset window improves on all three sweeps. The measured drag-rise onsets also land in exactly the order and position Eq. 8 predicts (M_crit 0.625/0.654/0.687). All of this is machinery validation on one airfoil from one source: the paper's constants come only from the full pre-registered fit.

## What is deliberately NOT done

No Phase A battery, no full calibration fit, no holdout scoring, no Phase C measurement, and no Results/Discussion/Conclusion/Abstract text. The pilot numbers above stay out of Results.

## Future steps, in order

1. Mentor sign-off (Wednesday session): the deviations log D1-D10, the amendments A1-A12, the TN 3607 37-curve list, and the frozen McCroskey tier table.
2. TN 3607: convention table (it is cn, not cl), sanity gate, then the approved curves through the pipeline. This is the main calibration dataset.
3. TN 1546: convention table (wall-correction rule from its own Figure 2), then full digitization BEFORE the final fit is selected, with raised QC because its curves have no markers.
4. Remaining Ferri airfoils per the Methods cap (2-3 CD(M) runs each across several airfoils), each with its lift sheet in the same sitting.
5. Phase A battery per Step 6 (subsonic baseline vs TR-824, onset, magnitude, validity map, confidence audit), frozen as a complete paper before the definitive fit.
6. The full pre-registered Phase B fit (leave-one-source-out, quality-weighted, uncertainty-aware per A5), then the one-shot holdout scoring against Harris and TN 1546 and the Phase C coverage check, reported whatever they say.
7. Paper assembly items from the audit: AI-assistance disclosure, Limitations section, Data/Code Availability statements, back matter, the six missing citations, and the page-budget trim.
8. Boundary probes (TP-2890, RAE 2822) last; AGARD AR-138 needs a rights check before its points are redistributed.

## File map (all in the repository)

docs/: methods-section.md (frozen Methods and pre-registration), protocol-deviations.md (D1-D10, A1-A12), mccroskey-tiers.md, tn3607-curve-list.md, tn1546-scout.md, paper-outline-FINAL.md, proposal-updated-answers.md, project-handoff-brief.md.
data/: master-dataset.csv (the single read path, 92 rows), harris-fig8.csv, ferri-2309.csv, ferri-cl.csv, ferri-re.csv, ferri-qc-sample.csv, data-phase-report.md, results-view.html (the visual summary).
tools/: the extraction pipeline (harness.html, plotscan/rowband/trace/cluster/paths .ps1), build-master.ps1, and the pinned-path scripts (parity.py, pilot_fit.py, stock_exact.py, gate_ferri.py, gen_dataset.py).
evidence/: every scan crop the numbers were read from.
