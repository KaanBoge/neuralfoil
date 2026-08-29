# LUMIERE MASTER HANDOFF: The NeuralFoil Trustworthiness Study
### Complete state of the project, every result, and all extracted data
Compiled 2026-08-23. Author: Kaan Boge, Lumiere Research Program (mentored; final paper 12 to 20 pages; example journal Oxford Journal of Student Science).
Public repository: https://github.com/KaanBoge/kaanboge.github.io/tree/main/neuralfoil-study
Companion app: https://kaanboge.github.io/neuralfoil-studio.html

---

# HOW TO USE THIS FILE

Upload this file and say something like:

> "This is the complete state of my research project. Everything you may use is inside it, and you must not add any number, citation, or result that is not written here. The Introduction and Literature Review in Part 15 are finished text: refine them, do not replace them. The Methods in Part 5 are frozen. There are no Results yet, so do not write a Results, Discussion, Conclusion, or Abstract section. Never use em dashes. Help me with [the specific section you want]."

The single most important instruction to repeat is the one in Part 0.1: no invented numbers. This document contains every measurement the project has, and the paper's credibility rests on none of them being fabricated.

---

# PART 0. READ THIS FIRST (instructions for whoever writes the paper)

**0.1 Anti-fabrication rule.** Every number, citation, formula, and result you may use is in this document. Do not invent, estimate, round differently, or "recall" anything not written here. If a number you want is missing, it does not exist yet: say so or ask. Aerodynamic data is the core of this paper's credibility, and a single invented value destroys it.

**0.2 The hard boundary between done and not done.** The pre-registered study battery has NOT run. There is no Phase A battery, no full calibration fit, no holdout scoring, and no confidence calibration. Therefore the paper currently has NO Results section, NO Discussion of findings, NO Conclusion, and NO Abstract. What exists is: a finished Introduction and Literature Review (Part 15 of this document, near-final prose), a frozen Methods with pre-registration (Part 5), and a completed data-extraction and machinery-validation phase (Parts 7 to 10). The pilot recalibration numbers in Part 9 are METHODS VALIDATION, not findings, and must never be presented as the study's results.

**0.3 Style rules (non-negotiable).**
- Never use em dashes (the "—" character) or double hyphens. Use commas, colons, or separate sentences.
- American spelling. APA citations.
- Journal density is about 500 words per page.
- Voice: plain, precise, honest. Claims are measured, never conferred. Limitations are stated, never hidden.
- Never use the words "guarantee," "prove," or "certify." The framing is that trustworthiness is measured and bounded, not proven. The paper repairs what can be repaired and bounds what cannot.

**0.4 How this document was verified.** Before delivery it was audited by three independent checkers working from the raw files rather than from the prose. One diffed all 466 numeric cells of the data tables in Part 8 against the source CSVs and found zero transcription errors, then recomputed the quality-control statistics independently. A second re-derived every arithmetic claim (the fold means, the percentage reduction) and checked every Methods and scouting claim against its source document. A third read for internal contradictions and for anything a paper-writer would still be missing. Their findings were applied, and several mattered: the sanity-gate errors were restated from 0.3 and 0.6 counts to 1.3 and 0.5 counts because the registered estimator is the plateau mean rather than a single point; the tunnel turbulence entry moved from n_crit 4.5 to 4.9 for the same reason; the measured drag-rise onsets were computed and added because the onset claim had been qualitative; a sentence in the literature review that described the wave-drag formula without its drag-divergence window was corrected, since it would have reintroduced an error the project had already caught once; and the plateau summary was recomputed over an explicitly stated window. Anything still marked as unresolved in this document is genuinely unresolved rather than overlooked.

**0.5 What is genuinely novel here (the claim to defend).** Not "the first correction of NeuralFoil." The precise claim is: the first calibration of NeuralFoil's transonic drag-rise layer against experimental data with quantified held-out error, the first validity map of NeuralFoil against wind-tunnel measurement, and the first audit of whether its confidence score tracks real experimental error.

---

# PART 1. PROJECT IDENTITY

**Working title:** From Black Box to Bounded Tool: An Experimental Audit, Recalibration, and Uncertainty Calibration of the NeuralFoil Aerodynamic Surrogate

**Research question:** Where does NeuralFoil disagree with wind-tunnel experiment; can its weakest layer, the transonic drag rise, be recalibrated to reduce error on data it has never seen; and can its self-reported confidence be turned into calibrated error bounds?

**Compact 20-word form:** "Where does NeuralFoil disagree with experiment, does recalibrating its transonic layer reduce held-out error, and is its confidence calibrated?"

**The four contributions:**
1. A validity map of NeuralFoil's error against experimental data, organized by flow regime and airfoil family.
2. The first audit of whether its confidence score tracks real experimental error, together with a conversion of that score into calibrated error bounds with measured coverage. Structural prediction: the score is blind above the critical Mach number by construction, because the network never sees the Mach number.
3. The first calibration of its drag-rise formula against experimental data with quantified held-out error, tested on an airfoil family excluded entirely from the fit.
4. A released, machine-readable dataset of the digitized measurements together with the calibration code (supporting contribution).

---

# PART 2. THE THREE-PHASE DESIGN AND THE PRE-REGISTRATION

**Phase A, the audit (validity map).** NeuralFoil's predictions compared against published wind-tunnel data at matched Mach number, Reynolds number, and transition state, at fixed lift coefficient. Deliverable: a validity-map figure (flow regimes against airfoil families; green, yellow, and red cells plus gray for "no public data"). Phase A is frozen as a complete, self-contained paper before any fitting begins.

**Phase B, the fix (recalibration).** The neural network stays frozen. Only the post-processing wave-drag formula is refit: up to three free parameters (leading coefficient, exponent, onset offset between predicted critical Mach and measured drag-rise onset). The fitting target is the drag-rise INCREMENT, never absolute CD. Robust least squares (soft-L1 loss), leave-one-source-out cross-validation, and a mandatory one-parameter null model that must be beaten.

**Phase C, the safety (uncertainty calibration).** Reuses Phase A's comparison points; no new data collection. Audits the STOCK pipeline only, meaning the shipped confidence score and the stock model's drag errors.

### The pre-registration box (verbatim, recorded before any fitting)

> - **Calibration data:** TN 3607 and Ferri WR L-143 only, with any 16-series entries excluded.
> - **Near holdout:** Harris TM-81927 (NACA 0012) plus the full 16-series family (TN 1546).
> - **Boundary probe:** SC(2)-0714 and RAE 2822, expected not to transfer, and reported as a limit of validity rather than a failure.
> - **One-shot rule:** the recalibrated model's holdout scoring and the Phase C coverage measurement each happen exactly once, in one pass, after model selection is final, and are reported whether or not they succeed. Stock-model comparisons on holdout sources appear earlier only as part of Phase A's validity map, which is by design.
> - **Success criteria (near holdout only):** at least a 30% reduction in mean absolute error of the drag-rise increment against the stock formula, and M_dd error cut in half, both judged against the McCroskey scatter band.
> - **No-harm check:** subcritical predictions unchanged.
> - **Confidence calibration (Phase C):** every Phase C quantity audits the stock pipeline, meaning the shipped confidence score and the stock model's drag errors, and is computed from calibration-set comparison points only; the two regimes are split at NeuralFoil's predicted M_crit, which exists for every prediction. Calibration target, fixed now: within each of five equal-count confidence bins per regime, the empirical frequency of absolute drag error at or below T = 20 drag counts (the same threshold as the drag-rise onset backup rule) is compared with the bin's mean confidence score, and the reported metric is the count-weighted mean absolute gap between the two, the expected calibration error. The conformal bound is the 90th percentile of absolute drag error over calibration-set points, per regime, fixed before the holdout is touched. Its coverage is then measured exactly once on holdout points, per regime, still against the stock pipeline; the bound is declared usable in a regime if coverage falls inside the exact two-sided 95% binomial interval around 90% for that regime's holdout point count (which approaches the 85% to 95% window only for large samples), and declared uninformative otherwise, with either outcome reported.

**One ambiguity in the frozen text, flagged rather than silently fixed.** The "Near holdout" bullet names both Harris and TN 1546, while the success-criteria bullet is scoped "near holdout only," and everywhere else in the study TN 1546 is called the family holdout and Harris the near holdout. So the frozen box does not say clearly whether the 30-percent and half-M_dd criteria apply to TN 1546 as well as to Harris. Because a pre-registration is not rewritten after the fact, this is recorded here as an ambiguity for the mentor to resolve in writing before the holdout is scored. The recommended resolution, consistent with every other document, is: near holdout = Harris, family holdout = TN 1546, and the success criteria apply to both, reported separately.

**Timestamp evidence.** The frozen Methods and this pre-registration were committed publicly to the study repository as commit 58e6877 before the definitive fit. The commit history is the audit trail.

---

# PART 3. WHAT NEURALFOIL IS (locked technical facts)

- NeuralFoil (Sharpe & Hansman, 2025, arXiv:2503.16323) is a neural network trained on about 7.9 million XFOIL solutions.
- **Inputs:** airfoil shape (CST/Kulfan parameters), angle of attack, Reynolds number, n_crit, forced-transition locations. **The Mach number is NOT a network input.**
- **Compressibility is post-processing only.** Corrections are applied to lift and moment; drag receives nothing below the critical Mach number.
- **The wave-drag layer, exactly as shipped (verified by reading the installed aerosandbox 4.2.10 source, kulfan_airfoil.py, get_aero_from_neuralfoil):** CD_wave = 80(M − M_crit)^4 applies only between M_crit and the drag-divergence Mach number mach_dd = M_crit + 0.068. Beyond drag divergence the code blends into a separate RANS-tuned term (a slope-50 form). This detail matters: an earlier version of our own analysis compared against the pure quartic extrapolated everywhere, which overstated the stock model's error. The honest comparator is the exact shipped pipeline evaluated by aerosandbox itself.
- A legacy generate_polars() path carries different constants and is never the reference.
- **M_crit** comes from a compact symbolic-regression surrogate (Eq. 8 of the NeuralFoil paper) applied to the predicted incompressible minimum pressure coefficient. Its constants in the current master source are 1.011571, 0.658243, 0.672479.
- **Outputs:** CL, CD, CM, Top_Xtr, Bot_Xtr, analysis_confidence, plus 32-station boundary-layer quantities per surface.
- **Speed:** about 30x faster than XFOIL for a single case, up to 1,000x in batches; always returns an answer where XFOIL sometimes fails to converge.
- **The authors' own words:** the drag-rise formula "typically errs on the side of over-estimating wave drag"; onset predictions are "reasonably trustworthy," wave-drag magnitude beyond that is not.
- **Prior transonic work, both simulation-only:** the author's own CFD-based retune (recorded in the AeroSandbox 4.2.4 changelog, never written up as a study) and KHRONOS (Sarker, Batley, Sarojini, & Saha, 2025, arXiv:2512.10287), a multi-fidelity kernel surrogate that USES NeuralFoil as a low-fidelity source and targets flow fields rather than correcting NeuralFoil's formulas. No published work has audited NeuralFoil against wind-tunnel data.

---

# PART 4. DATA SOURCES (corrected metadata, read from the reports themselves)

| Report | Year | Airfoils | Mach range | Reynolds number | Data form | Role |
|---|---|---|---|---|---|---|
| NACA TN 3607 (Daley & Dick) | 1956 | 6-series 64A family plus thickness-distribution variants (64A004/006/009/012; 64A206/506; 63A009/65A009/16-009) | up to 1.0 | up to 1.6 × 10⁶ | Plotted, normal-force coefficient cn | **Calibration (primary)** |
| NACA WR L-143 / ACR L5E21 (Ferri) | 1945 | 24 assorted sections, Guidonia open-jet tunnel | 0.40 to 0.94 | 0.34 to 0.42 × 10⁶, approximately constant | Plotted, true CL | **Calibration (increment-only)** |
| NACA TN 1546 (Lindsey, Stevenson & Daley) | 1948 | 24 NACA 16-series airfoils | 0.3 to 0.8 | 0.85 to 2.0 × 10⁶ | Plotted, faired curves without markers | **Family holdout** |
| NASA TM-81927 (Harris) | 1981 | NACA 0012, Langley 8-Foot Transonic Pressure Tunnel | 0.30 to 0.86 | 3 to 9 × 10⁶ | Plotted on fine grids | **Near holdout** |
| NASA TP-2890 (Jenkins) | 1989 | Supercritical SC(2)-0714 | 0.60 to 0.76 | 4 to 45 × 10⁶ | Tabulated | Boundary-of-validity probe |
| AGARD AR-138 | 1979 | RAE 2822 | about 0.68 to 0.75 | 6.5 × 10⁶ | Tabulated | Boundary-of-validity probe |
| NACA TM 1240 (Göthert) | 1949 | Symmetric and cambered series, DVL tunnel | high subsonic | see report | Plotted | Independent-facility cross-check |
| NACA TN 1813 (Nitzberg & Crandall) | 1949 | 0015, 23015, 4415, 65-series | supercritical | see report | Plotted | Drag-rise mechanism reference |
| NASA TM-100019 (McCroskey) | 1987 | NACA 0012 across 40+ tunnels | n/a | n/a | Curve fits and quality groups | Quality tiers and noise floor |
| NACA TR-824 (Abbott et al.) | 1945 | 4- and 5-digit, 6-series | low speed | 3 to 9 × 10⁶ | Plotted and tabulated | Subsonic baseline; critical-Mach charts are theory-only |

### 4.1 Three metadata corrections we made by reading the actual reports

**(a) "Tabulated" was wrong for Harris and Ferri.** Page-by-page reconnaissance of the NTRS scans (all 141 Harris pages, all 171 Ferri pages) found NO force-coefficient tables in either. Both are plotted figures only. Every study document was corrected. Everything is digitized.

**(b) Ferri's test conditions were wrong in our documents.** Reading the report text with page citations established: the 24-airfoil tests were made in the **Guidonia (Italy) 1.31 by 1.74 foot open-jet high-speed tunnel**, not the Langley 24-inch tunnel. Model chords were 1.575 in (4 cm) for thickness ratios of 8 percent or greater and 1.969 in (5 cm) for thinner sections. **The Reynolds number was held approximately CONSTANT in the band 0.34 to 0.42 million across the whole Mach range** by varying tunnel density (pressure 0.1 to 1.0 atm). Our documents had said "3.4 to 4.2 × 10⁶," a factor-of-ten error, now corrected everywhere. Lift is true section lift coefficient CL from a three-component semiautomatic balance (not normal-force coefficient), and drag came from the same balance, with no wake rake. Models were polished steel with no transition devices, so transition was free (the report never states this explicitly). Because the jet is open, closed-throat choking does not occur, and the report states data are essentially free from tunnel-wall effects up to M = 0.94 for these chord sizes. Figure scheme: Figures 23 to 46, three sheets per airfoil (CL vs M, then CD vs M, then Cm vs M); the NACA 2309 is the eleventh airfoil, so it is **Figure 33**, verified by reading the caption.

**(c) TN 3607 is not the 4-digit family.** Its sections are the NACA 6-series 64A family plus thickness-distribution variants (63A009, 65A009, and a 16-009), and it reports **normal-force coefficient cn**, not lift coefficient. Two consequences: the 16-009 is assigned to the holdout family and excluded from calibration per the pre-registration, and Harris (a 4-digit 0012) is properly described as a **conventional-section near holdout**, not literally "same-family."

---

# PART 5. THE FROZEN METHODS (complete text, paste-ready)

This is the finished Methods section, about 1,750 words, reproduced in full so it can be used directly. Refine it; do not rewrite it. The pre-registration box in Part 2 belongs inside it after Step 6 and must never be cut.

In this study, NeuralFoil's accuracy will first be mapped against published wind-tunnel data (Phase A), its transonic drag-rise formula will then be recalibrated against that data (Phase B), and its confidence score will be audited for calibration and converted into error bounds with measured coverage (Phase C, which reuses Phase A's comparison points and adds no new data collection). Because a calibration can look successful through overfitting alone, meaning it matches the calibration data's noise rather than the real physics, every decision that could bias the result is fixed in this section, before any fitting begins. The steps below are written so another researcher could repeat the work with free tools.

**Step 1. Pin the software and identify the exact code under test.** Install Python 3.11 or later and pin exact versions of neuralfoil, aerosandbox, scipy, pandas, and matplotlib in a requirements.txt. NeuralFoil is a neural network trained on about 7.9 million XFOIL data points. Mach number is not an input to the network itself: the network sees only incompressible flow, and a short post-processing layer applies compressibility corrections to lift and moment, while drag receives no correction below the critical Mach number. Instead, the code computes a critical Mach number M_crit, the freestream Mach at which flow over the airfoil first reaches the speed of sound, from the predicted minimum pressure coefficient, then adds a wave-drag term CD_wave = 80(M − M_crit)⁴ above it, reaching drag divergence at about M_crit + 0.068. This layer lives in AeroSandbox's kulfan_airfoil.py (get_aero_from_neuralfoil). Two rules are fixed now: all runs use the AeroSandbox interface, because the Mach input and the transition parameter n_crit exist only there, and the legacy generate_polars() path, which carries different constants, is never the reference.

**Step 2. Assemble the data sources and freeze the quality tiers.** All sources are free public reports, split in advance. The calibration set is NACA TN 3607 (thickness, camber, and thickness distribution varied, to M = 1.0, plotted) and Ferri WR L-143 (24 airfoils, M = 0.40 to 0.94, plotted per-airfoil figures in the NTRS scan). Three groups are held out and hidden from all fitting. Harris NASA TM-81927 (NACA 0012, M = 0.30 to 0.86, plotted in the NTRS scan) is an independent-facility near-holdout check on a classic conventional section. The entire 16-series family, all of NACA TN 1546 (M = 0.3 to 0.8), is the true family holdout. The supercritical SC(2)-0714 (NASA TP-2890) and RAE 2822 (AGARD AR-138) are pre-registered, meaning declared in writing before any fitting, as a test of where the method is expected to break down. McCroskey's NASA TM-100019, a meta-analysis of over 40 wind tunnels, assigns each source a quality tier and sets the experimental scatter "noise floor"; tiers are frozen now and never used as fitting truth. The M_crit charts in TR-824 are theory, used only as a consistency check.

**Step 3. Write a convention table per source, then pass a sanity gate.** Before extracting data from a source, record three things: whether it plots normal-force coefficient (cn) or lift coefficient (cl); whether transition, the point where airflow along the surface trips from smooth to turbulent, was left free or fixed by a trip strip, and how that maps to n_crit (checked with an n_crit sweep); and the tunnel's Mach-correction convention. Points near tunnel choking are excluded. Then one subcritical point from that source must match NeuralFoil's subsonic prediction within 10 drag counts in CD and 0.05 in CL before bulk extraction is allowed. This gate catches a mistake when it costs one point, not five hundred.

**Step 4. Build one master dataset with provenance.** All sources are plotted in the public NTRS scans (a reconnaissance pass of every page of Harris and Ferri found no force-coefficient tables), so everything is digitized. Extract Harris and Ferri first, selected figures only: drag-divergence summaries plus two to three fixed-CL CD(M) runs each, so a minimum dataset always exists. Digitize with WebPlotDigitizer v4 or an equivalent grid-calibrated extraction method whose axis anchors are recorded, capped at a mentor-approved figure list of roughly 35 to 40 curves, or about 500 points. Ten percent of points are digitized twice, independently, to quantify digitization error. Every point carries provenance columns [report, figure, airfoil, family, t/c, camber, Re, Mach, transition, CL, CD, quality_tier] in one master CSV, and every later figure reads from this file.

**Step 5. Fix the comparison and M_dd extraction rules.** Every comparison is matched-condition: same Mach, Reynolds number, and transition state, at fixed lift coefficient rather than fixed angle of attack. Fixed-CL values come from a precomputed angle-of-attack sweep with monotone interpolation, a smooth fill-in between computed points that never invents wiggles, restricted to M ≤ 0.9 and the pre-buffet CL range. The experimental drag-divergence Mach M_dd, where drag begins rising steeply, is never obtained by finite-differencing noisy digitized points. Instead, a cubic polynomial in Mach is fit to each CD(M) sweep and differentiated. If a sweep has fewer than four points beyond drag-rise onset, a backup rule applies: M_dd is where drag rises 20 counts (one drag count = 0.0001 in CD) above the subcritical plateau. Whichever rule a sweep triggers is recorded in the master CSV and applied identically in calibration and holdout scoring. It is fixed here because it defines the success criterion.

**Step 6. Run the Phase A battery and freeze Phase A.** Each block produces one table and one figure. (a) Subsonic baseline: 3 to 4 anchor airfoils versus TR-824 wind-tunnel data, scored by mean absolute error in CL and in CD in drag counts (the pitching moment stays outside scope, as the review states). (b) Onset: NeuralFoil's M_crit and predicted drag-rise onset versus measured M_dd. (c) Magnitude: the ratio of predicted to measured wave drag against (M − M_crit), the figure that motivates Phase B. (d) Confidence audit and calibration (Phase C, which shares this battery's comparison points): the confidence score never sees the compressibility correction, so it cannot detect errors added there. The reliability diagram, expected calibration error, and split-conformal bound are computed exactly as the pre-registration box specifies, from calibration-set points only, and the bound is stated as "with 90% coverage, drag error is within N counts." The frozen Phase A paper includes this audit and the bound itself; only the bound's one-shot holdout coverage check waits for Step 10. The deliverable is a validity-map figure, flow regimes against airfoil families, with green, yellow, and red cells plus a gray "no public data" state. Phase A is frozen as a complete, self-contained paper before any fitting begins.

*[The pre-registration box from Part 2 of this handoff is inserted here.]*

**Step 7. Reimplement the stock transonic layer standalone.** The compressibility block is rewritten as transonic_patch.py, consuming only Cp_min, incompressible CD, t/c, CL, and Mach. Before any constant changes, it must reproduce AeroSandbox's outputs to machine precision, proving the calibration targets the real pipeline and nothing else.

**Step 8. Define the fitting target and candidate models before fitting.** The fitting target is the drag-rise increment ΔCD_exp(M), which is CD_exp(M) minus the same source's own measured subcritical baseline for the same airfoil and CL, never absolute CD. This subtraction removes per-tunnel offsets and NeuralFoil's incompressible drag bias. Candidate forms are fixed in advance: a mandatory one-parameter null model, k · 80(M − M_crit)⁴; F1, A(M − M_crit)^b; F2, a Korn-equation-anchored form with a fitted M_dd offset; and F3, coefficients linear in t/c and CL. The parameter cap is three, extendable to five only if the cross-validation of Step 9 supports it.

**Step 9. Fit and select by leave-one-source-out cross-validation.** Fitting uses robust least squares (scipy's soft_l1 loss), which reduces the pull of outlier points, weighted by McCroskey quality tier. Selection uses cross-validation, meaning the fit is tested on data it was not trained on: fit on all calibration sources but one, test on the excluded source, then swap. With two calibration sources this is a two-fold swap, which is why adoption is gated by beating the null model rather than by the cross-validation score alone. Effective sample size is reported as sweep curves and sources, never raw point counts, because points within one sweep are not independent.

**Step 10. Evaluate the holdout once, decompose, and release.** The selected model is scored on the holdout exactly once against the pre-registered criteria, and the boundary probe is reported separately as the expected limit of validity. In the same single pass, the Phase C conformal bounds are checked for coverage on the holdout points, per regime, against the stock pipeline and the pre-registered binomial window. A decomposition refit follows, in which the same form is fit once using experimentally derived M_crit instead of NeuralFoil's; this separates "M_crit is biased" from "the drag-rise shape is wrong." The no-harm check confirms subcritical predictions are unchanged. Every figure is regenerated by script, pinned versions are recorded in the paper, and the dataset CSV and calibration code are released openly. Constants calibrated this way belong to this composite pipeline, meaning the network plus the M_crit formula plus the drag-rise formula, and not to transferable physics. The claim is deliberately narrow: the first calibration of this layer against experimental data with quantified held-out error. Two pieces of prior work are cited alongside it, the author's own CFD-based retune recorded in the AeroSandbox 4.2.4 changelog, and KHRONOS (Sarker, Batley, Sarojini, & Saha, 2025), a multi-fidelity surrogate that blends high-fidelity CFD with NeuralFoil-generated low-fidelity data rather than correcting NeuralFoil's own formulas.

**Two amendments to fold into the text when it is next revised** (both are dated protocol amendments, Part 6): Step 2's description of TN 3607 no longer says "4-digit," because the report's sections are the 6-series 64A family; and Step 3's n_crit sweep range is 3 to 14, not 7 to 11, because the measured facility values fall below the original range.

---

# PART 6. PROTOCOL DEVIATIONS AND PROPOSED AMENDMENTS

This log exists because a pre-registered study stays honest only if departures are declared, dated, and justified, never silently patched. Status of the holdouts: Harris has been used only for Phase-A-style stock-model comparison at the sanity gate and for the free-transition n_crit convention entry (see D4). No model constant has ever been fitted to it. TN 1546 has not been opened beyond structural scouting.

### Deviations already made

**D1 (2026-08-22). Ferri failed the absolute sanity gate; extraction proceeded.** Step 3 requires a subcritical match within 10 drag counts before bulk extraction. Ferri failed by roughly 45 to 60 counts at every plausible Reynolds number and n_crit. Extraction proceeded and the source was demoted to increment-only use. The frozen text contains no such exception; this was a judgment call, not compliance. Rationale: the offset is consistent with the known low-Reynolds, high-turbulence character of this small 1945 open-jet tunnel. See amendment A8 for the replacement gate.

**D2 (2026-08-23). A pilot fit ran before Phase A was frozen.** The Methods fix "Phase A is frozen before any fitting begins." A machinery-validation pilot fit ran on Ferri calibration data first. Commitments: it touched no holdout data; the candidate form list, parameter cap, and Phase A content remain exactly as pre-registered; its constants are machinery validation, not findings.

**D3 (2026-08-22). Fixed-alpha extraction versus the fixed-CL comparison rule.** Step 5 requires comparisons at fixed CL; the extracted sweeps are fixed-alpha as plotted. For Harris (symmetric 0012 at alpha −0.14 deg, CL about 0) this is immaterial. For the cambered 2309 it is a real deviation, now remedied: the companion CL-vs-M figure was digitized so every drag point receives its measured CL (Part 8.3).

**D4 (2026-08-22). n_crit found outside the declared sweep range, using holdout subcritical data.** Step 3 declares an n_crit sweep of 7 to 11; the Harris free-transition plateau matches n_crit about 4.5, below that range, and the entry was tuned on a Harris subcritical point. Defenses recorded: the entry affects only the subcritical baseline level, while the Phase B target is the increment above that baseline, which insulates holdout scoring; and the tuned value will be validated on at least one additional free-transition subcritical point not used in the tuning. Amendment A12 extends the declared range.

**D5 (2026-08-22). Harris fixed-9e6 series demoted one quality tier.** Decided at the gate stage, before any fitting existed. The justification on record is physical (trip overdrag: plateau about 30 counts above the other fixed series, and the series appears only above M about 0.5), matching the caveat in Harris's own report and in McCroskey; the 36-count gate disagreement was the trigger for inspection, not the justification.

**D6 (2026-08-22). Extraction preceded the complete Ferri convention table.** Step 3 requires the convention table first; the Reynolds curve and lift convention were read only after the pilot extraction. Backfill completed 2026-08-23.

**D7 (2026-08-22 to 23). Browser engine used where the Methods pin the Python AeroSandbox path.** The sanity gates and the pilot's M_crit values first ran on the verified browser port of NeuralFoil. All of it has since been reproduced on the pinned Python path, and the parity is exact (Part 9.5). The browser port's role is cross-check and interactive exploration, not reference.

**D8 (2026-08-22). Digitization tool.** Step 4 named WebPlotDigitizer; the actual pipeline is custom machine gridline detection plus independent label-anchored reads (Part 7), which exceeds WebPlotDigitizer's auditability because every axis anchor is recorded and every read is re-checkable against archived evidence crops. The Methods' "equivalent grid-calibrated method" clause covers this.

**D9 (2026-08-23). Independent-QC correction of the first Ferri read.** The first manual read of the 2309 diamond curve carried a 5 to 8 count glyph-top bias and, above M 0.78, had slid onto the adjacent square curve. An independent re-read caught both; the dataset was replaced. Lesson adopted as practice: same-reader double-reads do not catch curve misassignment, so the Step 4 double-read quota is implemented as independent-reader re-reads.

**D10 (2026-08-23). Source-metadata corrections from reading the actual reports.** The Guidonia tunnel, chord sizes, constant low Reynolds number, true-CL convention, TN 3607's 6-series identity and cn convention, and TN 1546's truncated scan. All detailed in Part 4.1 and Part 10.

### Proposed amendments (pre-declared, awaiting mentor sign-off, before any further fitting)

**A1. Plateau estimator, fixed.** Baseline = mean CD over all sweep points with M ≤ (measured onset − 0.05), minimum 3 points. Plateau uncertainty = standard error of that mean, propagated into every ΔCD of the sweep as a fully correlated component. The window is defined from the data, never from NeuralFoil's predicted M_crit.

**A2. M_dd rule completed.** Primary: cubic fit in M over [plateau end − 0.05, last point ≤ 0.90], with M_dd where dCD/dM = 0.10. Backup (fewer than 4 points beyond onset): the plateau + 20 counts crossing. The rule used is recorded per sweep. M_dd uncertainty from refits under per-point (u_cd, u_M) perturbations.

**A3. Aggregation unit for success criteria.** MAE computed per sweep, then unweighted mean across sweeps; sweep and source counts always reported. This prevents long sweeps from dominating.

**A4. Secondary comparators pre-declared.** Besides the exact stock pipeline: the fitted one-parameter null k·80(M−Mc)^4 and the legacy constant form 20(M−Mc)^4.

**A5. Uncertainty-aware weighting.** Per-point sigma² = u_cd² + (local dCD/dM × u_M)² + plateau common-mode term, used in fit weights and reported next to held-out MAE. Fitted-parameter uncertainties via bootstrap (400 resamples, resampling at sweep level).

**A6. Conformal bound finite-sample form.** The Phase C bound uses the split-conformal order statistic ceil((n+1)×0.9) of absolute drag error, not the plain 90th percentile; ECE reported with a sweep-level bootstrap interval.

**A7. Phase C robustness companion.** The registered one-shot binomial coverage check stays primary; a sweep-level block bootstrap of coverage is pre-declared as the robustness analysis, because points within a sweep are not independent.

**A8. Increment-mode gate (replaces D1's ad-hoc disposition).** A source failing the absolute gate may enter increment-only use if its subcritical plateau drifts ≤ 5 counts over the plateau window AND its measured drag-rise onset falls within 0.03 of NeuralFoil's predicted M_crit at matched conditions. Applied to Ferri retroactively (both conditions hold) and to all future sources prospectively.

**A9. Master dataset schema.** One merged master CSV with sweep_id; numeric alpha_nominal (the Ferri "−1,0" merged curve carried as alpha_nominal 0 with an alpha_plotted note); numeric Re per point; CL per point; tier_source (McCroskey, frozen) split from tier_extraction (per-point A/B/C); double_read flag with second-read delta; mdd_rule per sweep. The per-figure CSVs remain the raw layer; a merge script is the single read path. **Implemented and populated (Part 8.5): all 92 rows now carry tier_source (Harris series 1, the trip-contaminated 9e6 series 2 per D5, Ferri 3) and mdd_rule, so Step 9's tier weighting and Step 5's per-sweep rule are computable from the file alone.**

**A10. Holdout extraction timing.** TN 1546 digitization completes and freezes before the final Phase B fit is selected, so no extraction judgment call can be influenced by knowing the model's predictions.

**A11. Numeric noise floor.** Extracted from McCroskey before holdout scoring, with a stated transfer rule for non-0012 sections. **Implemented (Part 10.1).**

**A12. n_crit sweep range extended** from the declared 7 to 11, to 3 to 14, matching the physically plausible range for high-turbulence tunnels; values found outside 7 to 11 are reported as findings about the facility.

---

# PART 7. THE EXTRACTION PIPELINE (how every number was obtained)

No PDF tooling existed on the working machine, so the pipeline was built from scratch and is released with the study.

1. **Rendering.** A pdf.js harness page (`harness.html`) renders any page or sub-region of a scanned report to an image at a chosen scale, driven by headless Microsoft Edge, with results posted back to a small local HTTP server that writes them to disk. Contact-sheet mode renders whole reports as thumbnail grids for cheap reconnaissance.
2. **Machine reading.** PowerShell scripts with inline C# (`plotscan.ps1`, `rowband.ps1`, `trace.ps1`, `cluster.ps1`, `paths.ps1`) load a rendered figure, threshold it, detect gridlines by darkness profiling (which measures the true grid pitch rather than assuming it), trace dark ink runs row by row, and cluster them into marker centroids and curve tracks.
3. **Local anchoring, because scans are skewed.** Values are never converted from global pixel coordinates. Gridlines are counted outward from a printed label near each point, and each point is measured against gridlines profiled inside its own micro-crop, which absorbs the roughly 10-pixel skew measured across a page.
4. **Independent second reads.** A separate reader (with no access to the first reader's values) re-reads a sample, and the spread quantifies digitization error. This is what caught the D9 error.
5. **Archived evidence.** Every crop that a value was read from is stored in the repository, so any point can be re-checked against the original figure.

Practical limits discovered: the pdf.js harness fails silently above render scale 16; halftone-printed figures (Harris) saturate at high zoom in dense regions, while 1940s line-art figures (Ferri) stay clean; and NTRS PDFs occasionally carry a 436-byte junk prefix that must be stripped before the file is a valid PDF (this affected TN 3607 and TN 1813).

---

# PART 8. THE DATA (complete, every extracted point)

Units: CD and CL are dimensionless section coefficients. One drag count = 0.0001 in CD. `u_cd` and `u_M` are one-sigma reading uncertainties. Extraction tier: A = clean marker, machine-verified; B = marker overlapped or line-traced; C = marker swallowed by an overlap, value partly inferred.

## 8.1 Harris NASA TM-81927, Figure 8 (page 58): NACA 0012, alpha = −0.14 deg. HOLDOUT, never fitted

Four series: Reynolds 3, 6, and 9 million with fixed transition (trip strips), plus 3 million with free transition. Grid pitch machine-verified at 0.0025 in cd and 0.025 in M per heavy line. In the knee (M 0.76 to 0.80) the four printed curves merge into one band, so points there carry band-level flags and looser series assignment; this is a property of the print, not of the extraction, and it matches McCroskey's warning about scatter in this regime.

**Series 1: Re = 3.0 × 10⁶, transition FIXED (circle glyph)**

| M | CD | u_cd | tier | note |
|---|---|---|---|---|
| 0.301 | 0.00900 | 0.0002 | A | circle glyph confirmed visually |
| 0.457 | 0.00906 | 0.0002 | A | |
| 0.489 | 0.00914 | 0.0002 | A | |
| 0.519 | 0.00915 | 0.0002 | A | |
| 0.569 | 0.00913 | 0.0002 | A | |
| 0.705 | 0.00975 | 0.0003 | B | line-trace, no discrete marker resolved |
| 0.730 | 0.00980 | 0.0003 | B | |
| 0.755 | 0.01018 | 0.0004 | B | entering knee |
| 0.790 | 0.01210 | 0.0008 | C | knee band; strand assignment by continuity only |
| 0.818 | 0.02070 | 0.0003 | A | circle glyphs confirmed in knee crop |
| 0.830 | 0.02900 | 0.0006 | B | |
| 0.840 | 0.03110 | 0.0002 | A | circle endpoint confirmed visually |

**Series 2: Re = 6.0 × 10⁶, transition FIXED (square glyph)**

| M | CD | u_cd | tier | note |
|---|---|---|---|---|
| 0.358 | 0.00791 | 0.0003 | A | glyph partly saturated |
| 0.403 | 0.00790 | 0.0003 | A | |
| 0.460 | 0.00800 | 0.0003 | B | markers merged with line |
| 0.520 | 0.00805 | 0.0003 | B | |
| 0.580 | 0.00810 | 0.0003 | B | |
| 0.705 | 0.00842 | 0.0003 | B | |
| 0.740 | 0.00824 | 0.0004 | B | |
| 0.762 | 0.00834 | 0.0004 | B | |
| 0.800 | 0.01300 | 0.0004 | A | marker at rise base |
| 0.810 | 0.01530 | 0.0003 | A | open square confirmed in knee crop |
| 0.840 | 0.03360 | 0.0002 | A | square endpoint; highest CD of all series |

**Series 3: Re = 9.0 × 10⁶, transition FIXED (diamond glyph).** Trip-overdrag contaminated, demoted one quality tier (deviation D5)

| M | CD | u_cd | tier | note |
|---|---|---|---|---|
| 0.520 | 0.01110 | 0.0005 | B | series appears only above M about 0.50 |
| 0.560 | 0.01110 | 0.0005 | B | |
| 0.705 | 0.01100 | 0.0003 | A | strong track |
| 0.730 | 0.01099 | 0.0003 | A | |
| 0.775 | 0.01350 | 0.0008 | C | knee band |
| 0.790 | 0.01130 | 0.0010 | C | non-monotonic vs 0.775; band ambiguity dominates |
| 0.818 | 0.01730 | 0.0003 | A | diamond glyph confirmed in knee crop |
| 0.826 | 0.02350 | 0.0010 | C | series terminates near M 0.825 to 0.83; no 0.84 endpoint |

**Series 4: Re = 3.0 × 10⁶, transition FREE (plus glyph)**

| M | CD | u_cd | tier | note |
|---|---|---|---|---|
| 0.301 | 0.00630 | 0.0002 | A | plus glyph confirmed visually |
| 0.354 | 0.00613 | 0.0002 | A | |
| 0.482 | 0.00612 | 0.0002 | A | |
| 0.516 | 0.00601 | 0.0002 | A | |
| 0.534 | 0.00601 | 0.0002 | A | |
| 0.579 | 0.00602 | 0.0002 | A | |
| 0.640 | 0.00633 | 0.0002 | A | |
| 0.667 | 0.00631 | 0.0002 | A | |
| 0.688 | 0.00631 | 0.0002 | A | |
| 0.695 | 0.00625 | 0.0002 | A | |
| 0.735 | 0.00650 | 0.0003 | B | |
| 0.757 | 0.00675 | 0.0003 | B | onset of gentle rise |
| 0.774 | 0.00728 | 0.0004 | B | |
| 0.785 | 0.00890 | 0.0004 | A | wide plus-profile marker |
| 0.791 | 0.00916 | 0.0004 | A | |
| 0.840 | 0.02960 | 0.0002 | A | plus endpoint confirmed visually |

**Mach uncertainties:** u_M is 0.003 for A-tier rows below about M 0.70, 0.004 for A-tier rows in and above the knee, 0.004 to 0.006 for B-tier rows, and 0.006 to 0.008 for the C-tier knee-band rows. (Do not state a single blanket value: 8 of the 47 rows are A-tier at 0.004.)

**Plateau summary, computed as the amendment-A1 mean over an explicitly stated window** (this replaces an earlier informal range that mixed two different windows and is not reproducible):

| Series | Plateau window | Points | Plateau mean CD | Spread across the window |
|---|---|---|---|---|
| free, 3 × 10⁶ | M ≤ 0.70 | 10 | **0.00618** | 0.00601 to 0.00633, drift 3.2 counts |
| fixed, 3 × 10⁶ | M ≤ 0.60 | 5 | **0.00910** | 0.00900 to 0.00915, drift 1.5 counts |
| fixed, 6 × 10⁶ | M ≤ 0.60 | 5 | **0.00799** | 0.00790 to 0.00810, drift 2.0 counts |
| fixed, 9 × 10⁶ | M ≤ 0.75 | 4 | **0.01105** | 0.01099 to 0.01110, drift 1.1 counts |

The 9 × 10⁶ window starts higher because that series is not plotted below M about 0.5. Every plateau drift is inside McCroskey's ±3-count untripped noise floor except the free series at 3.2 counts, which sits exactly on it.

## 8.2 Ferri NACA WR L-143, Figure 33 Continued (page 81): NACA 2309, Re = 3.8 × 10⁵. CALIBRATION, increment-only

Free transition. Grid: 0.005 in CD and 0.05 in M per line.

**Verification status, stated precisely.** The 15 alpha −1/0 points are the corrected independent re-read that replaced the D9 first read entirely. The alpha 1 and alpha 2 sweeps are single reads carrying an 8-point independent QC sample (Part 8.4). So 23 of the 45 points have been read by two independent readers and 22 have not. Do not describe all 45 as double-verified.

**Sweep A: alpha = −1 and 0 deg (plotted as one diamond curve)**

| M | CD | u_cd | tier |
|---|---|---|---|
| 0.400 | 0.0116 | 0.0005 | A |
| 0.500 | 0.0116 | 0.0004 | A |
| 0.600 | 0.0115 | 0.0004 | A |
| 0.650 | 0.0121 | 0.0004 | A |
| 0.700 | 0.0120 | 0.0004 | A |
| 0.720 | 0.0136 | 0.0008 | B |
| 0.750 | 0.0158 | 0.0005 | A |
| 0.780 | 0.0170 | 0.0005 | A |
| 0.800 | 0.0185 | 0.0005 | A |
| 0.822 | 0.0232 | 0.0007 | A |
| 0.845 | 0.0296 | 0.0006 | A |
| 0.869 | 0.0342 | 0.0006 | A |
| 0.897 | 0.0485 | 0.0009 | B |
| 0.920 | 0.0661 | 0.0008 | B |
| 0.941 | 0.0742 | 0.0008 | A |

**Sweep B: alpha = 1 deg (square curve)**

| M | CD | u_cd | tier |
|---|---|---|---|
| 0.400 | 0.0141 | 0.0006 | B |
| 0.501 | 0.0140 | 0.0005 | B |
| 0.601 | 0.0140 | 0.0005 | B |
| 0.650 | 0.0139 | 0.0004 | A |
| 0.700 | 0.0149 | 0.0004 | A |
| 0.750 | 0.0169 | 0.0005 | A |
| 0.780 | 0.0191 | 0.0004 | A |
| 0.800 | 0.0209 | 0.0004 | A |
| 0.820 | 0.0242 | 0.0005 | A |
| 0.848 | 0.0330 | 0.0005 | A |
| 0.870 | 0.0364 | 0.0006 | A |
| 0.898 | 0.0539 | 0.0006 | A |
| 0.919 | 0.0719 | 0.0007 | B |
| 0.939 | 0.0796 | 0.0008 | B |

**Sweep C: alpha = 2 deg (circle curve)**

| M | CD | u_cd | tier |
|---|---|---|---|
| 0.400 | 0.0179 | 0.0007 | B |
| 0.500 | 0.0175 | 0.0008 | C |
| 0.600 | 0.0178 | 0.0006 | B |
| 0.650 | 0.0196 | 0.0006 | A |
| 0.700 | 0.0220 | 0.0006 | A |
| 0.720 | 0.0239 | 0.0006 | A |
| 0.750 | 0.0250 | 0.0007 | A |
| 0.765 | 0.0249 | 0.0007 | A |
| 0.780 | 0.0260 | 0.0006 | A |
| 0.800 | 0.0263 | 0.0007 | B |
| 0.820 | 0.0300 | 0.0008 | B |
| 0.850 | 0.0401 | 0.0012 | C |
| 0.870 | 0.0461 | 0.0007 | A |
| 0.899 | 0.0639 | 0.0008 | A |
| 0.920 | 0.0792 | 0.0009 | B |
| 0.941 | 0.0877 | 0.0008 | A |

All rows carry u_M = 0.004 (one row, M 0.897, carries 0.003).

## 8.3 Ferri Figure 33 first sheet (page 80): CL versus Mach for the same airfoil

Digitized to satisfy the fixed-CL comparison rule (deviation D3). u_CL is 0.010 for M ≤ 0.80, then 0.012 to 0.015 at M 0.82, then 0.020 to 0.030 from M 0.85 onward through the lift break.

| M | CL (α=−1°) | CL (α=0°) | CL (α=1°) | CL (α=2°) |
|---|---|---|---|---|
| 0.40 | 0.095 | 0.195 | 0.285 | 0.390 |
| 0.50 | 0.098 | 0.199 | 0.290 | 0.395 |
| 0.60 | 0.105 | 0.209 | 0.300 | 0.405 |
| 0.65 | 0.112 | 0.219 | 0.307 | 0.415 |
| 0.70 | 0.122 | 0.236 | 0.320 | 0.430 |
| 0.72 | 0.126 | 0.242 | 0.328 | 0.440 |
| 0.75 | 0.133 | 0.248 | 0.340 | 0.455 |
| 0.78 | 0.136 | 0.254 | 0.350 | 0.465 |
| 0.80 | 0.132 | 0.250 | 0.348 | 0.463 |
| 0.82 | 0.122 | 0.220 | 0.332 | 0.448 |
| 0.85 | 0.078 | 0.145 | 0.275 | 0.380 |
| 0.87 | 0.010 | 0.075 | 0.215 | 0.320 |
| 0.90 | −0.065 | −0.070 | 0.050 | 0.150 |
| 0.92 | −0.100 | −0.075 | 0.020 | 0.130 |
| 0.94 | −0.085 | −0.050 | 0.040 | 0.185 |

Two facts worth using. First, lift rises with Mach through the plateau (the Prandtl-Glauert-like compressibility gain), peaks near M 0.78, and then breaks down sharply, which is the classic shock-induced lift break. Second, the lift gate passes where the drag gate failed: the measured CL at alpha 0 and M 0.40 is 0.195, and NeuralFoil at the true Reynolds number predicts 0.203 at n_crit 4, a difference of 0.008 against the gate's 0.05 CL criterion. The agreement is n_crit dependent (at n_crit 9 the prediction rises to 0.284 and would fail), and n_crit 4 is the physically appropriate setting for a small high-turbulence 1945 tunnel, which is the same direction the Harris free-transition entry pointed. The honest statement is therefore: **at the transition setting this facility's character implies, lift agrees while drag is offset by about 50 counts, which localizes the discrepancy to drag rather than to the extraction or the geometry.**

## 8.4 The independent QC double-read sample (quantifies digitization error)

Eight points on the two newest sweeps, re-read by an independent reader with label-anchored calibration.

| Sweep | M | First read CD | QC read CD | Difference (counts) |
|---|---|---|---|---|
| alpha 1 | 0.400 | 0.0141 | 0.0141 | 0.0 |
| alpha 1 | 0.800 | 0.0209 | 0.0210 | 1.0 |
| alpha 1 | 0.919 | 0.0719 | 0.0720 | 1.0 |
| alpha 1 | 0.939 | 0.0796 | 0.0794 | 2.0 |
| alpha 2 | 0.500 | 0.0175 | 0.0175 | 0.0 |
| alpha 2 | 0.820 | 0.0300 | 0.0300 | 0.0 |
| alpha 2 | 0.850 | 0.0401 | 0.0405 | 4.0 |
| alpha 2 | 0.941 | 0.0877 | 0.0876 | 1.0 |

**Mean absolute difference 1.1 counts; maximum 4.0 counts**, and the maximum falls on the single point both readers flagged as glyph-merged. This is the quantified digitization error for this figure.

## 8.5 The master dataset

`master-dataset.csv`, 92 rows, is the single read path for all later analysis (amendment A9). Columns: sweep_id, report, figure, airfoil, family, tc_percent, camber, Re, mach, transition, alpha_nominal, alpha_plotted, CL, CD, tier_source, tier_extraction, double_read, method, u_cd, u_M, mdd_rule, role, notes. Sweep ids are H8-3F, H8-6F, H8-9F, H8-3free (Harris) and F33-a0, F33-a1, F33-a2 (Ferri). The `role` column marks each row "holdout" or "calibration-increment-only," which is the machine-readable enforcement of the one-shot rule. **Double-read coverage is 31 of 92 points, 33.7 percent, against the Methods' 10 percent requirement.** The frozen source tiers are carried in the file: tier_source 1 for the three clean Harris series, 2 for the trip-contaminated 9 × 10⁶ series (the D5 demotion, recorded in-file rather than only in prose), and 3 for the three Ferri sweeps. The mdd_rule column records which Step 5 rule each sweep triggers (cubic for six sweeps, the +20-count backup for the short Harris 9 × 10⁶ series).

---

# PART 9. RESULTS OF THE WORK SO FAR (methods validation, NOT study findings)

## 9.1 The pre-registered sanity gate on Harris (Step 3)

NACA 0012, alpha = −0.14 deg, trips at 0.05 chord for the fixed-transition series. Gate threshold: 10 drag counts. Step 3 defines the gate on a single subcritical point, so both readings are given below: the named single point, and the amendment-A1 plateau mean from Part 8.1, which is the more conservative and the one to quote.

| Series | Experiment (A1 plateau mean) | Single gate point | NeuralFoil | Error vs plateau mean | Verdict |
|---|---|---|---|---|---|
| fixed, Re 3 × 10⁶ | 0.00910 | 0.00900 at M 0.301 | 0.00897 | **1.3 counts** (0.3 against the single point) | **PASS** |
| fixed, Re 6 × 10⁶ | 0.00799 | 0.00800 at M 0.460 | 0.00794 | **0.5 counts** (0.6 against the single point) | **PASS** |
| fixed, Re 9 × 10⁶ | 0.01105 | 0.01110 at M 0.520 | 0.00742 | **36.3 counts** | **FAIL**, exactly as the trip-drag caveat predicts; series demoted one tier (D5) |
| free, Re 3 × 10⁶ | 0.00618 | 0.00630 at M 0.301 | 0.00512 at n_crit 9 | 10.6 counts | resolved by the n_crit sweep below |

Both fixed-transition passes land inside two drag counts against an independent 1981 dataset, and one of them inside one count. That is a strong Phase-A-style result for the subsonic baseline. Quote 1.3 and 0.5 counts, not the single-point figures, because the plateau mean is the estimator the study registered in amendment A1.

## 9.2 The n_crit sweep (tunnel turbulence calibration)

NeuralFoil free-transition CD for the 0012 at Re 3 × 10⁶, alpha −0.14:

| n_crit | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|
| CD | 0.00684 | 0.00644 | 0.00614 | 0.00587 | 0.00561 | 0.00536 | 0.00512 | 0.00489 | 0.00467 |

The measured plateau crosses this curve between **n_crit 4.5 and 4.9**: the A1 plateau mean of 0.00618 crosses at n_crit 4.87, and the single lowest-Mach point of 0.00630 crosses at 4.47. **Quote n_crit ≈ 4.9**, because the A1 mean is the registered estimator; report the 4.5 to 4.9 range as the sensitivity. This becomes the convention-table entry for the Langley 8-Foot Transonic Pressure Tunnel, and with it the free-transition gate passes by construction. Note the value lies below the pre-registered 7-to-11 sweep range (deviation D4, amendment A12), which is itself the finding: this facility behaves as a higher-turbulence tunnel than the default assumption.

## 9.3 The Ferri gate at the true Reynolds number

NACA 2309, alpha 0, measured CD 0.0116. NeuralFoil at the documented Guidonia conditions:

| Reynolds | n_crit 4 | n_crit 6 | n_crit 9 |
|---|---|---|---|
| 0.34 × 10⁶ | 0.00716 (44.4 counts low) | 0.00677 (48.3) | 0.00676 (48.4) |
| 0.38 × 10⁶ | 0.00703 (45.7) | 0.00648 (51.2) | 0.00644 (51.6) |
| 0.42 × 10⁶ | 0.00696 (46.4) | 0.00624 (53.6) | 0.00617 (54.3) |

**Verdict: fails the absolute gate by 44 to 54 counts at every plausible setting, so Ferri is increment-only.** A uniform offset of this size cannot be explained by transition settings; it is the signature of a small 1945 open-jet tunnel operating near Reynolds 0.4 million, which is why McCroskey grades data of this era and scale in his lowest group. The lift comparison passes (Part 8.3), which localizes the problem to drag.

## 9.4 Onset validation (the first genuine physics result)

Critical Mach numbers from the exact AeroSandbox formula at the true Reynolds number, against measured onsets computed from the data in Part 8.2. Two onset definitions are given because they answer different questions: the +5-count departure marks where the drag first leaves its plateau (the physical onset, comparable to M_crit), while the +20-count crossing is the registered A2 backup rule for drag divergence (which by construction lands later, and is comparable to M_crit + 0.068).

| Sweep | Predicted M_crit | Measured onset (+5 counts) | Gap to M_crit | Measured M_dd (+20 counts, A2 backup) | Predicted M_dd (M_crit + 0.068) |
|---|---|---|---|---|---|
| alpha 2 | 0.6246 | **0.611** | 0.014 | 0.652 | 0.693 |
| alpha 1 | 0.6542 | **0.682** | 0.028 | 0.728 | 0.722 |
| alpha 0 / −1 | 0.6871 | **0.703** | 0.015 | 0.721 | 0.755 |

**The measured onsets appear in the same order as the prediction (alpha 2 first, then alpha 1, then alpha 0) and every one falls within 0.03 of the predicted critical Mach number.** This is the first quantitative support in this study for the NeuralFoil authors' own claim that onset prediction is trustworthy even where magnitude is not, and it is also what qualifies Ferri for increment-only use under amendment A8.

**Implementation cross-check, stated precisely** (an earlier draft of this document conflated two different comparisons): the Kármán-Tsien numerical route agrees with the browser app's Eq. 8 implementation within 0.003, and the app's Eq. 8 agrees with the shipped AeroSandbox formula within about 0.010 (the largest single gap is the alpha 1 sweep, 0.664 versus 0.6542). The two independent routes to M_crit therefore agree to about one part in seventy, which cross-validates the implementations without implying they are identical.

## 9.5 Engine parity (deviation D7 closed)

The browser port of NeuralFoil used for interactive work reproduces the pinned Python path (neuralfoil 0.3.3, aerosandbox 4.2.10, WSL Python 3.14.4) **exactly, to all five decimal places**, on all six 0012 sanity-gate cases and on the 2309 CL, CD, and Cp_min values. The Step 7 concern for the subsonic network is closed; the standalone transonic-layer reproduction (Step 7 proper) still awaits Phase B.

## 9.6 The recalibration pilot (calibration data only; Harris never loaded)

Setup: fitting target is the drag-rise increment ΔCD above each sweep's own subcritical baseline, restricted to M ≤ 0.90 per the frozen Methods, using scipy least_squares with soft_l1 loss on the pinned path. Leave-one-sweep-out: fit on two sweeps, score on the third, three times.

Per-sweep parameters used: baselines 0.01170 (alpha 0), 0.01403 (alpha 1), 0.01770 (alpha 2); M_crit 0.6871, 0.6542, 0.6246; transonic point counts 9, 8, 11. Each baseline is the mean over that sweep's points below M_crit − 0.03, which is amendment A1's rule applied with the predicted rather than the measured onset. Under A1 as finally worded (measured onset minus 0.05) the alpha 0 window is M ≤ 0.653 and the baseline is unchanged at 0.01170; the other two are unchanged as well.

**One honest wrinkle to report, found in verification.** Across the alpha 0 plateau window the drag drifts 6.0 counts (0.0115 at M 0.600 to 0.0121 at M 0.650), which marginally exceeds the 5-count drift condition proposed in amendment A8. The other two sweeps drift 1.0 and 4.0 counts and pass. Two readings are defensible and the mentor should pick one in writing: either the alpha 0 plateau window ends at M 0.60 (making the baseline 0.01157 and the drift 1.0 count), or the 5-count threshold is too tight given McCroskey's own ±3-count noise floor on far better data, in which case A8's threshold should be restated relative to that floor. This does not change the pilot's conclusions (a 1.3-count baseline shift against increments of 100 to 350 counts), but it is exactly the kind of detail that must be declared rather than smoothed over.

| Model | Held-out MAE per fold (α0 / α1 / α2) | Mean |
|---|---|---|
| **Exact shipped pipeline** (aerosandbox 4.2.10, quartic to drag divergence then RANS blend) | 154.7 / 303.1 / 314.9 | **257.6 counts** |
| **Null**, k·80(M−Mc)^4, fitted k = 0.122 (effective constant 9.8, versus the shipped 80) | 77.8 / 43.2 / 79.1 | **66.7 counts** |
| **F1 (selected)**, ΔCD = 1.314 (M−Mc)^2.607 | 58.3 / 32.9 / 57.8 | **49.7 counts** |

F1 beats the null on every fold and cuts the exact-stock error by 81 percent out-of-sample. F2 was not needed at this scale; **F1o** (the onset-offset variant) fit its offset to exactly 0 and was dropped by parsimony, which is itself informative: at these conditions the predicted M_crit needed no shift.

**No-harm check.** The refit term is structurally zero below M_crit, so every subcritical prediction, including the two sub-count gate passes, is unchanged bit for bit. In the onset window [M_crit, M_crit + 0.05], MAE improves on all three sweeps: 10.5 to 10.0, 5.1 to 4.4, and 18.7 to 18.1 counts.

**Scope honesty, mandatory whenever these numbers are mentioned.** One airfoil, one source, free transition, low Reynolds number. The cross-validation spans angle of attack, not airfoils, so it tests generalization across loading, not across geometry. This demonstrates the Phase B machinery end to end and indicates the direction and rough size of the correction. The paper's constants come only from the full pre-registered fit.

**Audit-trail note.** Three passes were run as understanding improved: first against a pure quartic extrapolated everywhere (which unfairly overstated stock error at 574 counts), then against the exact shipped pipeline at an assumed Reynolds number of 1 × 10⁶ (stock 231.2, null 77.7, F1 55.2 with A = 1.076, b = 2.44), and finally at the true Reynolds number of 0.38 × 10⁶, which produced the table above. Only the final numbers should be used; the earlier ones are recorded because a study that hides its corrections is not auditable.

---

# PART 10. SOURCE SCOUTING RESULTS

## 10.1 McCroskey NASA TM-100019: the frozen quality-tier table and noise floor

McCroskey sorts 40-plus NACA 0012 experiments into five groups. Group 1: conducted with the utmost care. Group 2: agree with both the Group-1 lift and drag correlations (within ±0.0040 in β·Cl_alpha and ±0.0010 in Cd0). Group 3: agree in lift or drag but not both. Group 4: satisfy the criteria but with identified major problems, or fail them while still covering useful ranges. Group 5: examined but not used.

| Study source | McCroskey listing | Tier adopted here |
|---|---|---|
| Harris TM-81927 | **Group 2**, the first entry of his Table 2; text calls it "comparable in accuracy to Group 1," and his conclusions call it "the most satisfactory single investigation of the conventional NACA airfoils to date," with a recommendation to correct side-wall boundary-layer interference before using it for CFD validation | Tier 1, with the side-wall caveat carried into Limitations |
| Harris fixed 9e6 series | Trip contamination is discussed generally (trips "increase Cd... difficult to quantify"; other datasets demoted for thick trips) | Tier 2 (demoted per D5) |
| Ferri WR L-143 | **Not listed anywhere.** His nearest era analogues, the Langley 11-inch and 24-inch high-speed tunnel datasets, are both Group 5 | Tier 3, increment-only |
| TN 3607 | Not listed (not a 0012 test) | Tier 2 provisional, pending its own gate |
| TN 1546 | Not listed; its facility appears as Group 5 for a different 1949 dataset | Tier 3 provisional |
| TR-824 | LTPT tripped data noted for an "excessively thick trip" | Tier 2 untripped, Tier 3 tripped |

**The numeric noise floor (the honesty ceiling for every claim in this paper):**
- Untripped subcritical Cd0, Groups 1 and 2, for 1 × 10⁶ < Re < 3 × 10⁷: his fitted correlation holds to about **±0.0003 (3 counts)** (his page 9, summary point 1). His Group-1 fit itself has an rms standard error of 0.00005 and a maximum error of 0.0007 over its 36 points, and individual Group-1 points are precise to about ±0.0002 (his page 5).
- Tripped (fully turbulent) subcritical Cd0: about **±0.0005 (5 counts)** (his page 10, summary point 2).
- Drag-divergence Mach for the 0012: **M_dd = 0.77 ± 0.01**, with drag creep above M 0.72 (his page 8); maximum Cd0 of 0.11 ± 10 percent occurring between M 0.92 and 0.98 (his page 10).
- Transonic scatter between M 0.8 and 0.9: "the uncertainty in the measurements is virtually impossible to assess" (his page 8). Quote this when discussing knee-region uncertainty.
- Reference-standard context, as McCroskey reports it on his page 5: the AGARD-desired wind-tunnel drag accuracy is 0.0005 for configuration assessment and 0.0001 for CFD validation. Cite this as McCroskey citing AGARD, not as an AGARD source read directly.

**Transfer rule (amendment A11):** these bands are measured on the NACA 0012 only, so this study applies them to non-0012 conventional sections as a floor widened by 50 percent (4.5 counts untripped, 7.5 tripped), and states this. Note also that his correlations start at Re 1 × 10⁶, while Ferri sits at 0.38 × 10⁶ and parts of TN 1546 at 0.85 × 10⁶, below his range: another reason Ferri is increment-only.

## 10.2 TN 3607: figure inventory and the 37-curve mentor proposal

Ten airfoils. Thickness series 64A004, 64A006, 64A009, 64A012 (small duct); camber series 64A006, 64A206, 64A506; thickness-distribution series 63A009, 64A009, 65A009, 16-009 (large duct). Per-airfoil data are Figures 10(a) through 10(j), one page each, pages 37 to 46: cn, cd, and cm versus M at angles from −4 to 12 degrees. Cross-plots (Figures 11, 14, 15, 19, 21) re-present the same data versus cn or alpha. **Figure 17 on page 60 is the report's own drag-rise Mach summary (M_dr versus cn for all three families).** Every caption on pages 37 to 70 was legible; page 45 is rotated landscape.

**Proposed curve list for mentor approval (37 curves, inside the registered 35-to-40 cap), in priority order:**

| Priority | Page | Figure | Curves | Why |
|---|---|---|---|---|
| 1 | 37 | 10(a) | 64A004 cd(M) at alpha 0, 2 | Thinnest symmetric anchor of the thickness sweep |
| 2 | 40 | 10(d) | 64A006 cd(M) at alpha 0, 2 | Thickness step; also the camber series baseline, so it does double duty |
| 3 | 38 | 10(b) | 64A009 cd(M) at alpha 0, 2 | Thickness step; pivot to the distribution series |
| 4 | 39 | 10(c) | 64A012 cd(M) at alpha 0, 2 | Steepest drag rise; defines the thickness exponent |
| 5 | 41 | 10(e) | 64A206 cd(M) at alpha −2, 0, 2 | First camber step; brackets zero lift |
| 6 | 42 | 10(f) | 64A506 cd(M) at alpha 0, 2, 4 | Large camber step; straddles design lift |
| 7 | 60 | 17 | M_dr versus cn, all three panels (9 curves) | The authors' own drag-divergence fairing; cheap, and cross-checks our M_dd rule |
| 8 | 37-40 | 10(a-d) | cd(M) at alpha 4, all four symmetric sections | Lift dependence of drag rise, fitted rather than assumed |
| 9 | 43-46 | 10(g,i,j,h) | cd(M) at alpha 0 for 63A009, 65A009, 16-009*, 64A009 large duct | Thickness distribution at fixed t/c; the two 64A009 curves quantify the duct systematic |
| 10 | 43-46 | same | the same four at alpha 2 | Include if budget remains (running total 31 through priority 9: 2+2+2+2+3+3+9+4+4) |
| 11 | 41-42 | 10(e,f) | 64A206 at alpha 4, 64A506 at alpha 6 | Optional stretch to 37; drop first |

*The 16-009 belongs to the holdout family and is extracted for duct-systematic context only, never entered into the calibration fit.

Deliberately skipped: all cm figures (moment is out of scope), the cn-versus-alpha and polar cross-plots (the same data re-plotted, which would double-count), and the transonic similarity correlation (Figure 23, derived quantities).

## 10.3 TN 1546: family-holdout structure scout (no data values read)

50 pages. Text pages 3 to 16; Table I on page 17 is the airfoil-to-figure index; Table II on page 18 is the 16-009 ordinates. Figure 1 (page 19) compares wake-survey and force-test drag and is the only marker-per-point figure. Figure 2 (page 20) shows corrected versus uncorrected wall data for the 16-309. **Figures 3(a) through 3(x), pages 21 to 44, are the core: one airfoil per page, rotated 90 degrees, with cl versus M, cd versus M, and cm strips.** Figures 4(a) to 4(f), pages 45 to 50, are constant-Mach cross-plots.

**Critical finding: the NTRS scan truncates after Figure 4.** Figures 5 to 20 (lift-to-drag, critical-Mach, and force-break summaries, all listed in the report's own Table I) are absent. Any plan expecting them from this file fails; a second scan source would be needed.

The 24 airfoils, reconstructed from Table I (endpoints verified on-page as 3(a) = 16-009 and 3(x) = 16-1012): 16-009; 16-106, 16-109, 16-115, 16-130; 16-209, 16-215; 16-306, 16-309, 16-312, 16-315, 16-321; 16-409; 16-506, 16-509, 16-512, 16-515, 16-521, 16-530; 16-709, 16-712, 16-715; 16-1009, 16-1012. Thickness 6 to 30 percent, design lift 0 to 1.0.

Conditions: Langley 24-inch high-speed tunnel; duralumin models, 5-inch chord; M 0.3 to about 0.8; Re about 0.85 to 2.0 × 10⁶ varying with M; free transition implied (smooth models, no trips mentioned); **data are uncorrected for wall constriction, about 2 percent in M at supercritical speeds**, with Figure 2 giving the report's own corrected example; near-choking data omitted. Quoted accidental errors: cl ±0.005, cd ±0.0005, cm ±0.002, alpha ±0.1 degree. Angles of attack are non-integer, spaced 2 degrees with a −0.23 offset (−6.23, −4.23, −2.23, −0.23, 1.77, 3.77, 5.77, and up to 11.77 on cambered sections).

Digitization risk register: every Figure 3 page is rotated; the curves are faired with **no point markers**, so points must be sampled from curves and never extrapolated past an endpoint; alpha identity rides on five to seven similar dash patterns, which is the highest-risk judgment and demands raised QC; the wall-constriction correction must be handled in the convention table before comparisons; and choking arrows mark exclusion zones.

---

# PART 11. THE COMPANION APP (NeuralFoil Studio)

**URL:** https://kaanboge.github.io/neuralfoil-studio.html (single self-contained 3.2 MB HTML file, runs offline, no install).

**Headline capability:** the actual NeuralFoil 0.3.3 network (the exact nn-xlarge weight tensors, MIT licensed) runs live in the page. Selecting any airfoil computes a complete run (141 angles of attack by 6 Reynolds numbers) in about 150 milliseconds. The port re-implements airfoil normalization, the CST least-squares fit, the swish MLP, the Mahalanobis confidence penalty, and the flipped-evaluation symmetry average.

**Verification numbers that can be cited (all reproducible in-page):**
- Ported network versus the 846-case reference run: maximum differences CL 0.0029, CD 0.55 percent worst case, transition 0.0002, confidence 0.005. The residual is attributable to five-decimal rounding of the stored reference coordinates (a jitter test at that rounding level moves CL by up to 0.0054).
- Versus the pinned Python package: **exact agreement to five decimals** on the study's gate cases (Part 9.5).
- Hess-Smith panel solver versus the closed-form Joukowski exact solution: error falls monotonically with panel count (CL error 0.044 to 0.012 from 48 to 384 panels).
- Reality spot checks: E387 shows its documented mid-chord laminar separation bubble at Re 200k, reattaching at the predicted transition (0.563); S1223 gives CLmax 2.25 versus the published value of about 2.2; NACA 2412 gives CL 0.80 at 5 degrees and Re 200k, the published value.

**Thirteen tabs:** Flow (live 2D simulation with data-matched viscous field, Thwaites/Head boundary layer, real-CD wake, separation and bubble markers, particles, streamlines, pressure field, hover probe); 3D view (the 2D solution extruded, orbitable, with every Flow layer and an honest caption that no tip vortices or downwash are simulated); Polars (six charts, low-confidence shading, stall metrics, the clickable validity-map heatmap over the full 141 by 6 grid, CSV and JSON export); Pressure and transition (real Cp distributions, Kármán-Tsien Mach slider with sonic line and supersonic-pocket shading); Transonic lab (critical-Mach and wave-drag charts with the study's three pre-registered sliders, experimental CSV overlay, soft-L1 three-parameter fit validated by synthetic round-trip recovering truth A=120, b=3.5, offset 0.01 as 121/3.50/0.010, residual dashboard, 400-resample bootstrap with 95 percent intervals); Model sizes; Geometry (NACA designer plus family study: at Re 200k best lift-to-drag falls monotonically from 69 to 53 as thickness goes 6 to 24 percent); Compare; Flight lab; Checks (Squire-Young drag closure, pressure-integration lift audit, Michel transition correlation, Joukowski verification, ported-network verification); Digitizer (four-click affine axis calibration, rotation-tolerant, validated by exact round-trip on a synthetically rotated chart); Movie maker; About.

**Other facts:** all 1,655 UIUC airfoils searchable with hover previews; users can load their own .dat files; the analysis-conditions panel exposes n_crit (4 to 14) and forced trips as real network inputs (validated: n_crit 6 moves AG04 transition from 0.253 to 0.202; a trip at x/c 0.10 forces transition to 0.121); works on phones; exports render print-white.

**How the paper should use it:** one Methods paragraph presenting it as the companion artifact and reproducibility statement, with figures generated from its PNG exports and the verification numbers cited.

---

# PART 12. WHAT IS NOT DONE (the hard boundary)

Not done, and therefore not writable: the Phase A battery (all four blocks), the validity-map figure, the full pre-registered leave-one-source-out calibration fit, the one-shot holdout scoring against Harris and TN 1546, the boundary-probe evaluation, the Phase C confidence audit and coverage measurement, the M_crit decomposition refit, and the Step 7 standalone transonic-layer reproduction.

Consequently the paper has no Results, no Discussion of findings, no Conclusion, and no Abstract. The Introduction, Literature Review (Part 15), and Methods (Part 5) are complete.

---

# PART 13. FUTURE STEPS, IN ORDER

1. **Mentor sign-off** on the deviations log (D1 to D10), the twelve amendments (A1 to A12), the TN 3607 curve list, and the frozen McCroskey tier table.
2. **TN 3607 extraction:** convention table first (it reports cn, not cl), then the sanity gate, then the approved 37 curves through the pipeline. This is the main calibration dataset.
3. **TN 1546:** convention table (including the wall-correction rule from its own Figure 2), then full digitization with raised QC, completed and frozen **before** the final fit is selected, so no extraction judgment can be influenced by knowing the model's predictions.
4. **Remaining Ferri airfoils** per the Methods cap, each with its lift sheet digitized in the same sitting.
5. **Phase A battery** per Step 6, frozen as a complete paper before the definitive fit.
6. **The full Phase B fit** (leave-one-source-out, quality-weighted, uncertainty-aware per A5), then the one-shot holdout scoring and the Phase C coverage check, reported whatever they say.
7. **Paper-assembly items** (Part 14).
8. **Boundary probes** last (TP-2890 and RAE 2822). AGARD AR-138 needs a redistribution-rights check before its points enter the released dataset; the NACA and NASA sources are public-domain US government works.

**Future-work ladder for the Discussion, framed as outlook rather than promises:** propose winning constants upstream to AeroSandbox as a pull request; a follow-up conformal-calibration study turning confidence into per-prediction error bars; delta-learning, training a small correction network on errors in regimes the validity map flags; and true Mach-aware retraining on RANS data, with KHRONOS as adjacent prior art.

---

# PART 14. PAPER-ASSEMBLY REQUIREMENTS (from a four-lens reviewer audit)

These are the items a journal reviewer would demand and the paper does not yet have.

1. **AI-assistance disclosure (mandatory).** AI involvement was substantial: drafting and editing assistance, agent-based figure digitization and quality control, and the extraction tooling. Add a "Use of AI tools" statement naming what AI did and stating that the author verified all extracted values, code, and text. Mirror it in the Lumiere program paperwork.
2. **A Limitations section**, collecting caveats currently scattered: digitization uncertainty and the print-merged knee band; 1940s tunnel interference and low Reynolds numbers; two calibration sources meaning a two-fold cross-validation; constants tied to this composite pipeline rather than to transferable physics; the confidence score's structural blindness above M_crit; two-dimensional section data only; and the Harris side-wall interference caveat McCroskey raises.
3. **Data and Code Availability statements** pointing at the repository, with licenses (CC-BY 4.0 for data, MIT for code) and a planned Zenodo archive for a citable DOI.
4. **Back matter:** acknowledgments naming the Lumiere mentor and program, a single-author contribution statement clarifying what the mentor advised versus what the author executed, and a no-conflicts declaration.
5. **Missing citations to add:** the Korn equation (for candidate form F2, via Mason's transonic aerodynamics notes or Malone and Mason 1991); von Kármán (1941) for the Kármán-Tsien correction; a versioned URL-and-date citation for the AeroSandbox changelog; and software citations for AeroSandbox and for the digitization tooling. Also resolve the flagged item on the Drela (1989) volume and page numbers.
6. **Page budget.** The literature review at current depth is about 7.5 pages of text, and Methods about 3.5, which is roughly 12.5 pages before a single result. Either trim the review toward the 2,250-word option or move convention tables, extraction-protocol detail, and secondary tables to a supplement. Cap main-text figures at about eight.
7. **A "Protocol deviations" subsection in Methods**, summarizing Part 6, is what turns the deviations from a liability into evidence of rigor.

---

# PART 15. THE FINISHED PROSE (Introduction and Literature Review, near-final)

The following is complete, polished, paste-ready text of about 3,700 words. It has passed two adversarial review rounds. Refine it; do not replace it. Figure and table specifications follow the prose.

## 1. Introduction

Designing an aircraft means choosing an airfoil (the cross-sectional shape of a wing), and finding a good one means evaluating many candidates. The cost of each evaluation sets the pace of design. A wind-tunnel test, which measures the forces on a physical model in a controlled airstream, takes weeks. A computational fluid dynamics (CFD) simulation, which solves the equations of fluid motion numerically, takes hours. XFOIL, a fast physics-based program, takes seconds. NeuralFoil, a machine-learning tool published in 2025, takes milliseconds. That speed changes what design can be: an engineer can search thousands of shapes instead of comparing a handful. But it matters only if the tool's answers can be trusted, and this paper asks how far that trust should extend.

NeuralFoil (Sharpe & Hansman, 2025) is built around a neural network trained on millions of flow solutions generated by XFOIL. From an airfoil's shape, its angle of attack (its tilt relative to the oncoming air), and the Reynolds number (a measure comparing the flow's inertia to its viscosity), it predicts lift, drag, and pitching moment, and reports a confidence score meant to signal how far each prediction can be trusted. One structural detail matters more than any other. The Mach number, which is flight speed divided by the speed of sound, never reaches the network. The network sees only low-speed, incompressible flow. A post-processing layer adds compressibility afterward, but only to lift and moment. Predicted drag receives no compressibility correction at all until the flow passes an estimated critical Mach number, where a single empirical formula adds the sharp drag rise that appears near the speed of sound. That one formula is the whole of NeuralFoil's compressibility treatment of drag.

The gap lies in how the tool has been tested. Its published accuracy is measured mainly against XFOIL, the program that generated its training data. Testing a student only against their own teacher cannot reveal the mistakes the two share. NeuralFoil's accuracy against independent wind-tunnel measurement has never been systematically published, and the concern is sharpest in that drag-rise formula, inherited from an approximate empirical relation rather than learned from data. Its authors are candid about this: the formula "typically errs on the side of over-estimating wave drag" (Sharpe & Hansman, 2025). Two later efforts have addressed NeuralFoil's transonic weakness, and both check simulation against more simulation. Measurement never enters. Section 2.6 examines them.

This study turns that gap into three connected questions. The first is a validity map: NeuralFoil's predictions will be compared against published wind-tunnel data across flow regimes and airfoil families, establishing where the tool is accurate, where it degrades, and whether its confidence score knows the difference. The second is a frozen-network recalibration: the network is left untouched, and only the constants of the drag-rise formula are refit to historical measurements. The refit is judged on held-out data, meaning data deliberately excluded from the fitting, so that the test measures real prediction rather than memorization. The third is an uncertainty calibration: the same experimental comparisons yield, for every prediction, both a confidence score and a measured error, which makes it possible to test whether the score is calibrated, meaning whether ninety percent confidence is right about ninety percent of the time, and to convert it into a bound a user can act on, of the form "with ninety percent coverage, the drag error is within a stated number of counts." Together the three ask one thing: whether a neural surrogate can be made trustworthy for engineering use, not by assuming its reliability but by measuring it, repairing what can be repaired, and bounding what cannot. The research question is: *Where does NeuralFoil disagree with wind-tunnel experiment; can its weakest layer, the transonic drag rise, be recalibrated to reduce error on data it has never seen; and can its self-reported confidence be turned into calibrated error bounds?*

Most of the measurements come from NACA high-speed programs of the 1940s and 1950s. Data recorded decades before machine learning existed will therefore be used to test a 2025 tool and, if the recalibration survives data withheld from the fit, to improve it. This study will produce four contributions: (1) a validity map of NeuralFoil's error against experimental data, organized by flow regime and airfoil family; (2) the first audit of whether its confidence score tracks real experimental error, a score computed by a network that never sees the Mach number and is therefore expected to go blind exactly where the tool is weakest, together with a conversion of that score into calibrated error bounds with measured coverage; (3) the first calibration of its drag-rise formula against experimental data with quantified held-out error, tested on an airfoil family excluded entirely from the fit; and (4) a released, machine-readable dataset of the digitized measurements together with the calibration code. The review that follows covers airfoil geometry and the NACA naming system, the coefficients used to compare airfoils, transonic drag rise, NeuralFoil and related machine-learning tools, the historical wind-tunnel record, and prior efforts to validate and correct such tools.

## 2. Literature Review

### 2.1 Airfoil geometry and the NACA families

Of everything an aerodynamicist can change, the airfoil's shape does the most work. Shape alone decides how air moves over the wing. It sets how the air accelerates over the upper and lower surfaces, which fixes the pressure distribution, and the pressure difference between the surfaces is what produces lift. Shape also decides whether the flow stays attached to the surface or separates from it: attached flow keeps drag low; separation makes drag climb sharply. Two terms recur below. The chord is the straight line from leading edge to trailing edge, and the angle of attack is the angle between the chord line and the oncoming air.

The most systematic early study of airfoil shape came from the National Advisory Committee for Aeronautics (NACA), NASA's predecessor, which tested families of airfoils designed to vary one geometric variable at a time. Its four-digit code makes each shape readable at a glance: the first digit gives maximum camber in percent of chord, the second its position in tenths of chord, and the last two the maximum thickness in percent of chord. NACA 2412, shown in Figure 1, therefore has 2% camber at 40% of the chord and is 12% thick.

Camber is the curvature of the airfoil's centerline. Adding camber shifts the pressure distribution, so the airfoil produces more lift at a given angle of attack. A cambered airfoil generates lift even at zero angle of attack; a symmetric one does not. Thickness is how far the upper and lower surfaces bulge from that centerline. Moderate thickness gives a wing structural depth and helps the flow stay attached at low speed. At high speed, thickness takes on a second, less forgiving role, which Section 2.3 examines.

That one-variable-at-a-time discipline left behind a structure this study depends on. NACA's airfoils, and the historical measurements of them, split cleanly into families. A drag-rise model can therefore be calibrated on some families and then judged on a family that contributed nothing to the fit, using airfoils it has never seen.

### 2.2 Measuring performance: the lift coefficient, drag coefficient, and lift-to-drag ratio

Raw lift and drag forces are not useful for comparing airfoils: a large wing moving fast produces far more lift than a small wing moving slowly, even when the two shapes are identical. To strip size and speed from the comparison, aerodynamicists divide the force per unit span by the dynamic pressure of the airflow (a measure of how hard the moving air pushes) and by the chord. The results are the section lift coefficient, CL, and the section drag coefficient, CD, which are dimensionless measures of the shape itself. Every quantity in this paper is a two-dimensional section coefficient, the form in which both NeuralFoil and the wind-tunnel reports used here give their results.

A high CL alone does not make an airfoil efficient. Almost any shape generates large lift at a steep angle of attack, usually at the cost of large drag, a price paid continuously in thrust and fuel. The better question is how much lift an airfoil delivers for each unit of drag, which is the lift-to-drag ratio, CL/CD. Figure 2 illustrates the distinction: an airfoil's most efficient operating point is where CL/CD peaks, not where CL is highest.

CD values for practical airfoils are small decimals, so engineers measure differences in a finer unit. One drag count equals 0.0001 in CD. A single count sounds negligible, but choices between competing airfoils regularly hinge on a handful, because small drag savings compound over every hour of flight. Drag counts set the accuracy bar a prediction tool must meet. They give every comparison in this paper a concrete scale.

These three quantities are what this study places side by side: NeuralFoil's predictions against published wind-tunnel measurements. NeuralFoil also predicts a pitching-moment coefficient, and several of the sources tabulate it, but the moment lies outside this study's scope. The comparison is fair only if conditions match, since an airfoil's coefficients depend on the Mach number, the Reynolds number, and surface conditions such as roughness. Comparing a prediction at one condition against a measurement at another would measure the mismatch, not the model.

### 2.3 Transonic drag rise and the critical Mach number

Section 2.1 left thickness with an unfinished job: its second, less forgiving role at high speed. That role begins with a phenomenon called transonic drag rise. As air flows over an airfoil's curved upper surface it accelerates, so the local flow moves faster than the freestream, the undisturbed air ahead of the wing. Air near the wing can therefore reach the speed of sound while the aircraft itself is still flying below it. The freestream Mach number at which the local flow first reaches Mach 1 is called the critical Mach number.

Past that point, a region of supersonic flow forms over the airfoil. It cannot slow smoothly back to subsonic speed. Instead it ends in a shock wave, an extremely thin region where the air abruptly decelerates and its pressure jumps. The energy lost across the shock appears as a new form of drag called wave drag, which adds to the friction and pressure drag already present.

The shock also disturbs the boundary layer, the thin layer of slow-moving air along the airfoil's surface. That layer begins laminar, meaning smooth and orderly, and at some point along the chord becomes turbulent. The location of that change is called transition. Because transition depends on surface roughness and on how disturbed the oncoming air is, two wind tunnels can measure different drag on the same airfoil, a point Section 2.5 returns to. The pressure rise across a strong shock can separate the boundary layer from the surface, adding still more drag and cutting lift. Just above the critical Mach number the shock is weak and wave drag stays small, but the shock strengthens quickly as speed increases. Together, wave drag and shock-induced separation make the drag coefficient climb steeply once the airfoil passes its drag-divergence Mach number, which lies slightly above the critical Mach number. Across the NACA high-speed measurements surveyed in Section 2.5, drag divergence for conventional sections falls roughly between Mach 0.7 and 0.9, depending mainly on thickness and camber.

Thickness and camber matter here because both make the local flow accelerate more. A thicker airfoil forces the air around a larger obstacle, and a more cambered airfoil speeds up the flow over its upper surface, so both reach sonic flow at a lower flight speed. This lowers the critical Mach number and shifts the drag rise to earlier Mach numbers, as Figure 3 illustrates. The relationship was charted early: the classic NACA compendium of section data (Abbott, von Doenhoff, & Stivers, 1945) plotted critical Mach number against airfoil family. Those charts, however, are theoretical predictions rather than measurements, and this study does not treat them as ground truth. NeuralFoil is built on subsonic methods and does not model shock waves directly, so the critical Mach number is the quantity it can estimate most credibly in this regime. This study therefore treats it as an indicator of where drag rise begins, not as a prediction of the rise itself.

### 2.4 NeuralFoil and machine-learning aerodynamic tools

Every aerodynamic analysis tool trades fidelity, meaning how closely it captures the real flow physics, against cost in time and computation. The classical fast airfoil tool is XFOIL (Drela, 1989), which pairs a panel method (a rapid way of computing the airflow around a shape) with a boundary-layer model for friction effects near the surface. Decades of comparison with wind-tunnel data have earned XFOIL wide trust: within its subsonic range, it is often as accurate as far more expensive simulations. Its key limitation is compressibility, which it handles only through approximate corrections, with no shock-wave physics.

NeuralFoil is one of a growing family of machine-learning aerodynamic tools. These range from physics-informed neural networks, which build the flow equations into the training so the network is penalized for violating physics (Wassing, Langer, & Bekemeyer, 2024), to networks that simply learn to predict forces from geometry and flow conditions (Moin, Khan, Mobeen, & Riaz, 2021; Cai, Fan, & Liu, 2024). NeuralFoil itself is a surrogate model of XFOIL: a fast model trained to reproduce the outputs of a slower one, built on nearly eight million XFOIL data points. It learns from data, but physics is built into its structure. The network is constructed so that a symmetric airfoil at zero angle of attack yields exactly zero lift and moment, to machine precision. It predicts lift, drag, and moment coefficients, a critical Mach number, and a confidence score, all in milliseconds, roughly 30 times faster than XFOIL for a single case and up to 1,000 times faster for large batches. It always returns a result, where XFOIL sometimes fails to converge. That speed makes this study possible. Comparing a tool against a wind-tunnel archive means running it at hundreds of matched conditions, and the recalibration stage re-runs those cases for every candidate set of constants. Table 1 summarizes how wind tunnels, CFD, XFOIL, and NeuralFoil trade fidelity for speed and cost.

These advantages come at a price. A surrogate can be no more reliable than its training data, so NeuralFoil inherits XFOIL's subsonic range of validity. As Figure 4 shows, the Mach number never reaches the network; compressibility is handled entirely in post-processing, where the developers report that the analytical corrections hold up to the critical Mach number. Predictions also degrade far from the training data, which the confidence score is intended to flag. That is a claim this study tests rather than assumes. The critical Mach number itself comes from a compact algebraic surrogate applied to the network's predicted incompressible minimum pressure coefficient. This study records it as the drag-rise indicator described in Section 2.3: a threshold the tool can locate even though it cannot model what lies past it.

### 2.5 The experimental record: wind-tunnel data as ground truth

Testing NeuralFoil against reality requires experimental data, and the richest source dates from the 1940s and 1950s, which makes it seventy to eighty years old. In those decades NACA tested whole airfoil families in high-speed wind tunnels, publishing lift and drag against Mach number over ranges reaching as high as Mach 1.0 in the most extensive programs. Two reports form the calibration set. Daley and Dick (NACA TN 3607) varied thickness, camber, and thickness distribution systematically across the NACA 6-series 64A family up to Mach 1.0 (reporting normal-force rather than lift coefficient), exactly the geometric variables this study examines; the one 16-series section it also carries, the 16-009, is assigned to the holdout family and excluded from calibration. Ferri (NACA WR L-143) tested twenty-four airfoils up to Mach 0.94 in the Guidonia open-jet high-speed tunnel at a deliberately constant, low Reynolds number near 0.4 million; in the public NTRS scan these results appear as per-airfoil plotted figures, so they are digitized under the same protocol as the other plotted sources, and the per-tunnel drag offset expected at that Reynolds number confines this source to drag-rise increments. Göthert (NACA TM 1240) tested symmetric and cambered sections in the German DVL tunnel, independent of NACA, and serves as a cross-facility check. Nitzberg and Crandall (NACA TN 1813) studied how drag rise develops once the critical Mach number is exceeded: the same modeling problem this study revisits with a modern tool.

Lindsey, Stevenson, and Daley (NACA TN 1546) tested twenty-four airfoils of the high-speed 16-series between Mach 0.3 and 0.8. The 16-series is designed on a different principle from the calibration sections, so it will be withheld from the fit in full and serve as this study's family holdout: the test of whether a calibration learned on one family transfers to a family the model has never seen. Two further datasets anchor the edges. Harris (NASA TM-81927) measured a NACA 0012 in the Langley 8-Foot Transonic Pressure Tunnel from Mach 0.30 to 0.86; the NTRS scan presents these results as plotted figures on fine grids, so they too are digitized rather than transcribed. McCroskey's meta-analysis places this dataset in his second-highest quality group and calls it the most satisfactory single investigation of the conventional NACA airfoils, which makes it the study's near holdout: a classic conventional section, measured decades later in a different facility, kept out of all fitting. The supercritical SC(2)-0714 (Jenkins, 1989) and the RAE 2822 (AGARD AR-138) follow a different design philosophy, shaped to delay and weaken shock waves. A calibration built on classic NACA sections is not expected to transfer to them; they are included to locate where the method breaks down, which is itself a result. Table 2 lists every source and its role.

Experiments carry error bars of their own. McCroskey (NASA TM-100019) compared NACA 0012 measurements from more than forty wind tunnels and found measurable disagreement between facilities even for this heavily tested airfoil, a spread explained partly by differing transition conditions. That scatter sets a noise floor: no model can be validated more precisely than experiments agree with each other. Near Mach 1 the walls of a small 1950s tunnel also interfere with the flow, and the tunnel can choke, meaning the test section itself reaches sonic speed and no longer represents free flight. Measurements from that regime therefore carry wider uncertainty than their published curves suggest. The Methods section sets out how that uncertainty is handled.

Most of these measurements survive only as plotted curves in scanned reports. Some plot the normal-force coefficient instead of the lift coefficient (the normal force acts perpendicular to the chord, not to the oncoming flow), or mix runs with different transition conditions, so each source needs a conventions check before use. The extraction procedure is described in the Methods. No machine-readable compilation of this archive exists, so every study that has wanted these measurements has re-digitized the same scans, usually without recording how. A released dataset is therefore a contribution in its own right, not a byproduct of this one.

### 2.6 Validating and improving surrogate models: prior work and the gap

NeuralFoil's authors report its accuracy primarily against XFOIL, its own training-data source. That is the right first test for a surrogate model, but it measures how faithfully the network learned its teacher, not whether the teacher matches reality. Agreement with XFOIL is not agreement with experiment. The authors are unusually transparent about this boundary: they trust the tool to indicate when transonic flow begins, yet state plainly that its drag-rise model tends to overestimate wave drag (Sharpe & Hansman, 2025).

What this study will recalibrate is small and fully visible. As Figure 4 shows, the network is frozen, meaning its internal weights never change. Above the critical Mach number, a separate formula adds wave drag. That formula is an empirical fourth-power relation: the added drag is modeled as growing with the fourth power of how far past the critical Mach number the flow has gone, a form used in drag-divergence estimates since the 1970s. In the current analysis path it reads CD,wave = 80(M − Mcrit)⁴, applied over the interval between the critical Mach number and drag divergence, above which the shipped code blends into a separate term tuned to RANS simulations; an older routine in the same package uses a different leading coefficient, so the exact implementation is recorded in the Methods. Recalibrating this layer means refitting three free parameters of that one expression: the leading coefficient, the exponent, and an offset between the predicted critical Mach number and the Mach number at which measured drag rise actually begins. It does not mean retraining a neural network. A fit of roughly three parameters is small enough to attempt with the quantity of experimental data these archives provide.

Two later efforts have addressed NeuralFoil's transonic behavior. Neither used experiment. NeuralFoil's own author retuned these constants against CFD solutions of two kinds: full-potential solvers, which are fast but ignore the air's viscosity, and RANS solvers, which model turbulence and are slower but more complete. That change lives only in a software changelog and was never written up as a study. Separately, Sarker, Batley, Sarojini, and Saha (2025) built KHRONOS, a multi-fidelity surrogate that blends sparse high-fidelity CFD data with low-fidelity predictions from NeuralFoil. It improves accuracy by combining fidelities, not by correcting NeuralFoil's own formulas, and it targets the flow field rather than the drag-rise relation. No published work has systematically mapped NeuralFoil's error against wind-tunnel data, audited whether its confidence score tracks real error, or calibrated the transonic formula to experiment with entire airfoil families held out. This study will attempt all three. The claim is deliberately narrow: not the first correction of NeuralFoil, but the first calibration of this layer against experimental data with quantified held-out error.

One structural fact makes the confidence audit worth running and gives it a prediction. The score comes from the network, and the network sees only the incompressible sub-problem. It has no access to the Mach number, the compressibility corrections, or the wave-drag term. Above the critical Mach number the score is therefore blind by construction: it cannot detect error in the very layer this study targets. The audit will test the score separately below and above that threshold, and locating where it stops being informative is itself part of the contribution. The study then goes one step further and converts the score into a stated error bound with measured coverage, so that a user can read it as a number of drag counts rather than as a promise.

## Figure and table specifications

**Figure 1.** NACA four-digit airfoil geometry, drawn to true scale from the exact NACA equations. (a) Thickness family: NACA 0006, 0012, and 0018 differ only in maximum thickness. (b) Camber family: NACA 0012, 2412, and 4412 share 12% thickness and differ only in camber; the dashed line is the camber line of NACA 4412.

**Figure 2.** Why efficiency is a ratio. (a) A conceptual drag polar (CL against CD); the steepest line from the origin that touches the polar marks the maximum lift-to-drag ratio. (b) The same data plotted as CL/CD. Curves use the standard parabolic drag-polar model with representative values, not measured data.

**Figure 3.** Conceptual illustration of transonic drag rise for a thinner (6% thick) and a thicker (12% thick) symmetric NACA airfoil at zero lift. Generated with the same empirical fourth-power wave-drag form used in NeuralFoil's post-processing layer; representative behavior, not measured data.

**Figure 4.** NeuralFoil's prediction pipeline. The neural network (blue) is frozen in this study. The Mach number enters only in the post-processing layer (orange). Summarized from Sharpe and Hansman (2025) and the NeuralFoil/AeroSandbox source code.

**Table 1.** Comparison of airfoil analysis methods.

| | Wind tunnel | CFD (RANS) | XFOIL | NeuralFoil |
|---|---|---|---|---|
| What it is | Physical experiment on a real model | Numerical solution of the flow equations | Panel method plus boundary-layer model | Neural network trained on about 8 million XFOIL data points |
| Time per case | Weeks (build and test) | Hours | Seconds | Milliseconds |
| Cost | Very high | High (computing) | Free | Free |
| Handles shock waves | Yes | Yes | No; subsonic corrections only | No; inherits XFOIL's limits, but reports a critical Mach number |
| Always gives an answer | n/a | Sometimes fails to converge | Sometimes fails to converge | Always, with a confidence score |
| Role in this study | Source of reference measurements | Not used | The method NeuralFoil approximates | Main analysis tool |

**Table 2.** Use the corrected source table in Part 4 of this document.

**New figures now possible from the data in Part 8:** (a) the Harris four-series drag rise with NeuralFoil's gate predictions overlaid; (b) the n_crit sweep with the measured plateau crossing; (c) the Ferri three-sweep drag rise against the NeuralFoil prediction band; (d) the collapse plot, all three sweeps' ΔCD against (M − M_crit) with the stock, null, and refit curves. A rendered version of all four exists as `results-view.html` in the repository.

---

# PART 16. REFERENCES (APA, verified)

Abbott, I. H., von Doenhoff, A. E., & Stivers, L. S. (1945). *Summary of airfoil data* (NACA Report 824). https://ntrs.nasa.gov/citations/19930090976

AGARD. (1979). *Experimental data base for computer program assessment* (AGARD-AR-138). https://archive.org/details/DTIC_ADA073982

Cai, Z., Fan, Z., & Liu, T. (2024). *Efficient aerodynamic coefficients prediction with a long sequence neural network.* arXiv:2403.14979. https://arxiv.org/abs/2403.14979

Daley, B. N., & Dick, R. S. (1956). *Effect of thickness, camber, and thickness distribution on airfoil characteristics at Mach numbers up to 1.0* (NACA TN 3607). https://ntrs.nasa.gov/citations/19930084305

Drela, M. (1989). XFOIL: An analysis and design system for low Reynolds number airfoils. In T. J. Mueller (Ed.), *Low Reynolds number aerodynamics* (Lecture Notes in Engineering, Vol. 54, pp. 1–12). Springer. [Verify volume and page numbers before submission.]

Ferri, A. (1945). *Completed tabulation in the United States of tests of 24 airfoils at high Mach numbers* (NACA Wartime Report L-143; also NACA ACR L5E21). https://ntrs.nasa.gov/citations/19930092764

Göthert, B. (1949). *Airfoil measurements in the DVL high-speed wind tunnel (2.7-meter diameter)* (NACA TM 1240). https://ntrs.nasa.gov/citations/19930090916

Harris, C. D. (1981). *Two-dimensional aerodynamic characteristics of the NACA 0012 airfoil in the Langley 8-Foot Transonic Pressure Tunnel* (NASA TM-81927). https://ntrs.nasa.gov/citations/19810014503

Jenkins, R. V. (1989). *NASA SC(2)-0714 airfoil data corrected for sidewall boundary-layer effects in the Langley 0.3-meter Transonic Cryogenic Tunnel* (NASA TP-2890). https://ntrs.nasa.gov/citations/19890008197

Lindsey, W. F., Stevenson, D. B., & Daley, B. N. (1948). *Aerodynamic characteristics of 24 NACA 16-series airfoils at Mach numbers between 0.3 and 0.8* (NACA TN 1546). https://ntrs.nasa.gov/citations/19930082349

McCroskey, W. J. (1987). *A critical assessment of wind tunnel results for the NACA 0012 airfoil* (NASA TM-100019). https://ntrs.nasa.gov/citations/19880002254

Moin, H., Khan, H. Z. I., Mobeen, S., & Riaz, J. (2021). *Airfoil's aerodynamic coefficients prediction using artificial neural network.* arXiv:2109.12149. https://arxiv.org/abs/2109.12149

Nitzberg, G. E., & Crandall, S. (1949). *A study of flow changes associated with airfoil section drag rise at supercritical speeds* (NACA TN 1813). https://ntrs.nasa.gov/citations/19930082487

Sarker, A., Batley, R. T., Sarojini, D., & Saha, S. (2025). *A kernel-based resource-efficient neural surrogate for multi-fidelity prediction of aerodynamic field.* arXiv:2512.10287. https://arxiv.org/abs/2512.10287

Sharpe, P., & Hansman, R. J. (2025). *NeuralFoil: An airfoil aerodynamics analysis tool using physics-informed machine learning.* arXiv:2503.16323. https://arxiv.org/abs/2503.16323

Wassing, S., Langer, S., & Bekemeyer, P. (2024). *Physics-informed neural networks for transonic flows around an airfoil.* arXiv:2408.17364. https://arxiv.org/abs/2408.17364

**Still to add (Part 14, item 5):** the Korn equation source; von Kármán (1941) for the Kármán-Tsien correction; a versioned citation of the AeroSandbox changelog; software citations for AeroSandbox and the digitization tooling.

---

# PART 17. FILE AND REPOSITORY MAP

Repository: `kaanboge.github.io/neuralfoil-study` (commits 58e6877 and 46f9a10).

- **docs/** `methods-section.md` (frozen Methods with the pre-registration box), `protocol-deviations.md` (D1 to D10, A1 to A12), `mccroskey-tiers.md` (frozen tiers and noise floor with page citations), `tn3607-curve-list.md` (figure inventory and the 37-curve proposal), `tn1546-scout.md` (holdout structure scout), `paper-outline-FINAL.md` (Introduction and Literature Review), `proposal-updated-answers.md`, `project-handoff-brief.md`.
- **data/** `master-dataset.csv` (92 rows, the single read path), `harris-fig8.csv` (47 points), `ferri-2309.csv` (45 points), `ferri-cl.csv` (60 lift points), `ferri-re.csv`, `ferri-qc-sample.csv`, `data-phase-report.md`, `results-view.html` (the rendered visual summary), `everything-we-did.md`.
- **tools/** `harness.html` (pdf.js renderer), `plotscan.ps1`, `rowband.ps1`, `trace.ps1`, `cluster.ps1`, `paths.ps1` (extraction), `build-master.ps1` (merge script), `parity.py`, `pilot_fit.py`, `stock_exact.py`, `gate_ferri.py`, `gen_dataset.py` (pinned-path analysis).
- **evidence/** every rendered scan crop each value was read from, plus the reconnaissance contact sheets.

**Licenses:** data CC-BY 4.0, code MIT, documents all rights reserved pending submission. All source reports are public-domain US government works except AGARD AR-138, whose redistribution status must be checked before its points are released.

**Pinned environment:** WSL Ubuntu, Python 3.14.4 in `~/nfenv`, neuralfoil 0.3.3, aerosandbox 4.2.10, numpy 2.5.2, scipy.

---

*End of master handoff. Everything in this document is verified against the source reports, the installed code, or executed runs. Nothing in it is estimated.*


---

# PART 18. APPENDIX: THE RAW DATA FILES, VERBATIM

Everything above is the readable form. Below are the exact machine-readable files, so this single document is the whole dataset as well as the whole write-up. Copy any block into a .csv file and it works unchanged.

## A. master-dataset.csv (92 rows, the single read path for all analysis)

Columns: sweep_id, report, figure, airfoil, family, tc_percent, camber, Re, mach, transition, alpha_nominal, alpha_plotted, CL, CD, tier_source, tier_extraction, double_read, method, u_cd, u_M, mdd_rule, role, notes.

```csv
"sweep_id","report","figure","airfoil","family","tc_percent","camber","Re","mach","transition","alpha_nominal","alpha_plotted","CL","CD","tier_source","tier_extraction","double_read","method","u_cd","u_M","mdd_rule","role","notes"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.301","fixed","-0.14","-0.14","0","0.00900","1","A","TRUE","marker-machine+shape","0.0002","0.003","cubic","holdout","circle glyph confirmed visually at low-M tail"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.457","fixed","-0.14","-0.14","0","0.00906","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout","on circle plateau track x1220"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.489","fixed","-0.14","-0.14","0","0.00914","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.519","fixed","-0.14","-0.14","0","0.00915","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.569","fixed","-0.14","-0.14","0","0.00913","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.705","fixed","-0.14","-0.14","0","0.00975","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout","plateau line no discrete marker resolved"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.730","fixed","-0.14","-0.14","0","0.00980","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout",""
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.755","fixed","-0.14","-0.14","0","0.01018","1","B","FALSE","line-trace","0.0004","0.005","cubic","holdout","entering knee"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.790","fixed","-0.14","-0.14","0","0.01210","1","C","FALSE","band-strand","0.0008","0.006","cubic","holdout","knee band; strand assignment by continuity only"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.818","fixed","-0.14","-0.14","0","0.02070","1","A","TRUE","marker-machine+shape","0.0003","0.004","cubic","holdout","circle glyphs confirmed in knee crop"
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.830","fixed","-0.14","-0.14","0","0.02900","1","B","FALSE","line-trace","0.0006","0.005","cubic","holdout",""
"H8-3F","TM-81927","8","0012","4-digit","12","0","3.0e6","0.840","fixed","-0.14","-0.14","0","0.03110","1","A","TRUE","marker-machine+shape","0.0002","0.003","cubic","holdout","circle endpoint confirmed visually"
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.358","fixed","-0.14","-0.14","0","0.00791","1","A","FALSE","marker-machine","0.0003","0.003","cubic","holdout","on square plateau track x1265; glyph partly saturated"
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.403","fixed","-0.14","-0.14","0","0.00790","1","A","FALSE","marker-machine","0.0003","0.003","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.460","fixed","-0.14","-0.14","0","0.00800","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout","square track continuous; markers merged with line"
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.520","fixed","-0.14","-0.14","0","0.00805","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.580","fixed","-0.14","-0.14","0","0.00810","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.705","fixed","-0.14","-0.14","0","0.00842","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.740","fixed","-0.14","-0.14","0","0.00824","1","B","FALSE","line-trace","0.0004","0.004","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.762","fixed","-0.14","-0.14","0","0.00834","1","B","FALSE","line-trace","0.0004","0.005","cubic","holdout",""
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.800","fixed","-0.14","-0.14","0","0.01300","1","A","FALSE","marker-machine","0.0004","0.004","cubic","holdout","n22 marker at rise base"
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.810","fixed","-0.14","-0.14","0","0.01530","1","A","TRUE","marker-machine+shape","0.0003","0.004","cubic","holdout","open square glyph confirmed in knee crop"
"H8-6F","TM-81927","8","0012","4-digit","12","0","6.0e6","0.840","fixed","-0.14","-0.14","0","0.03360","1","A","TRUE","marker-machine+shape","0.0002","0.003","cubic","holdout","square endpoint confirmed visually; highest CD of all series"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.520","fixed","-0.14","-0.14","0","0.01110","2","B","FALSE","line-trace","0.0005","0.006","plus20ct","holdout","faint diamond track appears only above M~0.50; trip-overdrag elevated plateau | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.560","fixed","-0.14","-0.14","0","0.01110","2","B","FALSE","line-trace","0.0005","0.006","plus20ct","holdout","tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.705","fixed","-0.14","-0.14","0","0.01100","2","A","FALSE","line-trace","0.0003","0.004","plus20ct","holdout","strong track in upper piece | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.730","fixed","-0.14","-0.14","0","0.01099","2","A","FALSE","line-trace","0.0003","0.004","plus20ct","holdout","tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.775","fixed","-0.14","-0.14","0","0.01350","2","C","FALSE","band-strand","0.0008","0.006","plus20ct","holdout","knee band; continuity assignment | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.790","fixed","-0.14","-0.14","0","0.01130","2","C","FALSE","band-strand","0.0010","0.008","plus20ct","holdout","non-monotonic vs 0.775 row; band ambiguity dominates | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.818","fixed","-0.14","-0.14","0","0.01730","2","A","TRUE","marker-machine+shape","0.0003","0.004","plus20ct","holdout","diamond glyph confirmed in knee crop | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-9F","TM-81927","8","0012","4-digit","12","0","9.0e6","0.826","fixed","-0.14","-0.14","0","0.02350","2","C","FALSE","band-strand","0.0010","0.006","plus20ct","holdout","series terminates near M 0.825-0.83; no diamond endpoint at 0.84 | tier_source demoted 1 (deviation D5, trip overdrag)"
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.301","free","-0.14","-0.14","0","0.00630","1","A","TRUE","marker-machine+shape","0.0002","0.003","cubic","holdout","plus glyph confirmed visually at low-M tail"
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.354","free","-0.14","-0.14","0","0.00613","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.482","free","-0.14","-0.14","0","0.00612","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.516","free","-0.14","-0.14","0","0.00601","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.534","free","-0.14","-0.14","0","0.00601","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.579","free","-0.14","-0.14","0","0.00602","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.640","free","-0.14","-0.14","0","0.00633","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.667","free","-0.14","-0.14","0","0.00631","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.688","free","-0.14","-0.14","0","0.00631","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.695","free","-0.14","-0.14","0","0.00625","1","A","FALSE","marker-machine","0.0002","0.003","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.735","free","-0.14","-0.14","0","0.00650","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.757","free","-0.14","-0.14","0","0.00675","1","B","FALSE","line-trace","0.0003","0.004","cubic","holdout","onset of gentle rise"
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.774","free","-0.14","-0.14","0","0.00728","1","B","FALSE","line-trace","0.0004","0.005","cubic","holdout",""
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.785","free","-0.14","-0.14","0","0.00890","1","A","FALSE","marker-machine","0.0004","0.004","cubic","holdout","wide plus-profile marker n34"
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.791","free","-0.14","-0.14","0","0.00916","1","A","FALSE","marker-machine","0.0004","0.004","cubic","holdout","wide plus-profile marker maxlen56"
"H8-3free","TM-81927","8","0012","4-digit","12","0","3.0e6","0.840","free","-0.14","-0.14","0","0.02960","1","A","TRUE","marker-machine+shape","0.0002","0.003","cubic","holdout","plus endpoint confirmed visually"
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.400","free","0","-1,0","0.195","0.0116","3","A","TRUE","agent-QC label-anchored","0.0005","0.004","cubic","calibration-increment-only","CORRECTED 2026-08-23: replaces first manual read which was 5-8 counts high (glyph tops read instead of centers)"
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.500","free","0","-1,0","0.199","0.0116","3","A","TRUE","agent-QC label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.600","free","0","-1,0","0.209","0.0115","3","A","TRUE","agent-QC label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.650","free","0","-1,0","0.219","0.0121","3","A","TRUE","agent-QC label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.700","free","0","-1,0","0.236","0.0120","3","A","TRUE","agent-QC label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.720","free","0","-1,0","0.242","0.0136","3","B","TRUE","agent-QC label-anchored","0.0008","0.004","cubic","calibration-increment-only","marker printed small/faint; confirmed in three crops"
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.750","free","0","-1,0","0.248","0.0158","3","A","TRUE","agent-QC label-anchored","0.0005","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.780","free","0","-1,0","0.254","0.0170","3","A","TRUE","agent-QC label-anchored","0.0005","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.800","free","0","-1,0","0.25","0.0185","3","A","TRUE","agent-QC label-anchored","0.0005","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.822","free","0","-1,0","0.215","0.0232","3","A","TRUE","agent-QC label-anchored","0.0007","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.845","free","0","-1,0","0.157","0.0296","3","A","TRUE","agent-QC label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.869","free","0","-1,0","0.078","0.0342","3","A","TRUE","agent-QC label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.897","free","0","-1,0","-0.056","0.0485","3","B","TRUE","agent-QC label-anchored","0.0009","0.003","cubic","calibration-increment-only","steep region; M uncertainty dominates"
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.920","free","0","-1,0","-0.075","0.0661","3","B","TRUE","agent-QC label-anchored","0.0008","0.004","cubic","calibration-increment-only","congested cluster; glyph confirmed at 16x"
"F33-a0","WR-L143","33cont","2309","4-digit","9","2","380000","0.941","free","0","-1,0","-0.05","0.0742","3","A","TRUE","agent-QC label-anchored","0.0008","0.004","cubic","calibration-increment-only","endpoint; the previously reported 0.078 endpoint was the alpha=1 square glyph"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.400","free","1","1","0.285","0.0141","3","B","TRUE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only","overlaps alpha=-2 triangle through plateau; center from box edges | QC re-read delta 0.0 counts"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.501","free","1","1","0.29","0.0140","3","B","FALSE","agent label-anchored","0.0005","0.004","cubic","calibration-increment-only","overlaps alpha=-2 triangle"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.601","free","1","1","0.3","0.0140","3","B","FALSE","agent label-anchored","0.0005","0.004","cubic","calibration-increment-only","overlaps alpha=-2 triangle"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.650","free","1","1","0.307","0.0139","3","A","FALSE","agent label-anchored","0.0004","0.004","cubic","calibration-increment-only","clean glyph"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.700","free","1","1","0.32","0.0149","3","A","FALSE","agent label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.750","free","1","1","0.34","0.0169","3","A","FALSE","agent label-anchored","0.0005","0.004","cubic","calibration-increment-only",""
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.780","free","1","1","0.35","0.0191","3","A","FALSE","agent label-anchored","0.0004","0.004","cubic","calibration-increment-only",""
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.800","free","1","1","0.348","0.0209","3","A","TRUE","agent label-anchored","0.0004","0.004","cubic","calibration-increment-only","QC re-read delta 1.0 counts"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.820","free","1","1","0.332","0.0242","3","A","FALSE","agent label-anchored","0.0005","0.004","cubic","calibration-increment-only",""
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.848","free","1","1","0.279","0.0330","3","A","FALSE","agent label-anchored","0.0005","0.004","cubic","calibration-increment-only","alpha=-2 triangle directly above"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.870","free","1","1","0.215","0.0364","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.898","free","1","1","0.061","0.0539","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only","verified square at 20x zoom"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.919","free","1","1","0.022","0.0719","3","B","TRUE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only","verified at 24x; near-glyphs excluded by shape check | QC re-read delta 1.0 counts"
"F33-a1","WR-L143","33cont","2309","4-digit","9","2","380000","0.939","free","1","1","0.039","0.0796","3","B","TRUE","agent label-anchored","0.0008","0.004","cubic","calibration-increment-only","endpoint in dense cluster; separable from diamond and circle endpoints | QC re-read delta 2.0 counts"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.400","free","2","2","0.39","0.0179","3","B","FALSE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only","circle atop fused pair with alpha=-3 inverted triangle"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.500","free","2","2","0.395","0.0175","3","C","TRUE","agent label-anchored","0.0008","0.004","cubic","calibration-increment-only","almost fully overlapped with alpha=-3; center partly inferred | QC re-read delta 0.0 counts"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.600","free","2","2","0.405","0.0178","3","B","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only","inverted triangle just below"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.650","free","2","2","0.415","0.0196","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.700","free","2","2","0.43","0.0220","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.720","free","2","2","0.44","0.0239","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.750","free","2","2","0.455","0.0250","3","A","FALSE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only","alpha=3 curve line crosses marker"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.765","free","2","2","0.46","0.0249","3","A","FALSE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only","local flat spot in the rise"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.780","free","2","2","0.465","0.0260","3","A","FALSE","agent label-anchored","0.0006","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.800","free","2","2","0.463","0.0263","3","B","FALSE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only","partially fused with alpha=-2 triangle"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.820","free","2","2","0.448","0.0300","3","B","TRUE","agent label-anchored","0.0008","0.004","cubic","calibration-increment-only","alpha=-2 triangle fused just below | QC re-read delta 0.0 counts"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.850","free","2","2","0.38","0.0401","3","C","TRUE","agent label-anchored","0.0012","0.004","cubic","calibration-increment-only","marker swallowed by alpha=-3 overlap; from lower glyph plus curve line | QC re-read delta 4.0 counts"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.870","free","2","2","0.32","0.0461","3","A","FALSE","agent label-anchored","0.0007","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.899","free","2","2","0.156","0.0639","3","A","FALSE","agent label-anchored","0.0008","0.004","cubic","calibration-increment-only",""
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.920","free","2","2","0.13","0.0792","3","B","FALSE","agent label-anchored","0.0009","0.004","cubic","calibration-increment-only","round glyph verified at zoom"
"F33-a2","WR-L143","33cont","2309","4-digit","9","2","380000","0.941","free","2","2","0.185","0.0877","3","A","TRUE","agent label-anchored","0.0008","0.004","cubic","calibration-increment-only","endpoint; clean circle between alpha=3 and alpha=4 flags | QC re-read delta 1.0 counts"
```

## B. harris-fig8.csv (47 points, NASA TM-81927 Figure 8, HOLDOUT)

```csv
report,figure,airfoil,family,tc_percent,camber,Re,mach,transition,alpha_deg,CL_nominal,CD,quality_tier,method,uncertainty_cd,uncertainty_M,notes
TM-81927,8,0012,4-digit,12,0,3.0e6,0.301,fixed,-0.14,0,0.00900,A,marker-machine+shape,0.0002,0.003,circle glyph confirmed visually at low-M tail
TM-81927,8,0012,4-digit,12,0,3.0e6,0.457,fixed,-0.14,0,0.00906,A,marker-machine,0.0002,0.003,on circle plateau track x1220
TM-81927,8,0012,4-digit,12,0,3.0e6,0.489,fixed,-0.14,0,0.00914,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.519,fixed,-0.14,0,0.00915,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.569,fixed,-0.14,0,0.00913,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.705,fixed,-0.14,0,0.00975,B,line-trace,0.0003,0.004,plateau line no discrete marker resolved
TM-81927,8,0012,4-digit,12,0,3.0e6,0.730,fixed,-0.14,0,0.00980,B,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.755,fixed,-0.14,0,0.01018,B,line-trace,0.0004,0.005,entering knee
TM-81927,8,0012,4-digit,12,0,3.0e6,0.790,fixed,-0.14,0,0.01210,C,band-strand,0.0008,0.006,knee band; strand assignment by continuity only
TM-81927,8,0012,4-digit,12,0,3.0e6,0.818,fixed,-0.14,0,0.02070,A,marker-machine+shape,0.0003,0.004,circle glyphs confirmed in knee crop
TM-81927,8,0012,4-digit,12,0,3.0e6,0.830,fixed,-0.14,0,0.02900,B,line-trace,0.0006,0.005,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.840,fixed,-0.14,0,0.03110,A,marker-machine+shape,0.0002,0.003,circle endpoint confirmed visually
TM-81927,8,0012,4-digit,12,0,6.0e6,0.358,fixed,-0.14,0,0.00791,A,marker-machine,0.0003,0.003,on square plateau track x1265; glyph partly saturated
TM-81927,8,0012,4-digit,12,0,6.0e6,0.403,fixed,-0.14,0,0.00790,A,marker-machine,0.0003,0.003,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.460,fixed,-0.14,0,0.00800,B,line-trace,0.0003,0.004,square track continuous; markers merged with line
TM-81927,8,0012,4-digit,12,0,6.0e6,0.520,fixed,-0.14,0,0.00805,B,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.580,fixed,-0.14,0,0.00810,B,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.705,fixed,-0.14,0,0.00842,B,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.740,fixed,-0.14,0,0.00824,B,line-trace,0.0004,0.004,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.762,fixed,-0.14,0,0.00834,B,line-trace,0.0004,0.005,
TM-81927,8,0012,4-digit,12,0,6.0e6,0.800,fixed,-0.14,0,0.01300,A,marker-machine,0.0004,0.004,n22 marker at rise base
TM-81927,8,0012,4-digit,12,0,6.0e6,0.810,fixed,-0.14,0,0.01530,A,marker-machine+shape,0.0003,0.004,open square glyph confirmed in knee crop
TM-81927,8,0012,4-digit,12,0,6.0e6,0.840,fixed,-0.14,0,0.03360,A,marker-machine+shape,0.0002,0.003,square endpoint confirmed visually; highest CD of all series
TM-81927,8,0012,4-digit,12,0,9.0e6,0.520,fixed,-0.14,0,0.01110,B,line-trace,0.0005,0.006,faint diamond track appears only above M~0.50; trip-overdrag elevated plateau
TM-81927,8,0012,4-digit,12,0,9.0e6,0.560,fixed,-0.14,0,0.01110,B,line-trace,0.0005,0.006,
TM-81927,8,0012,4-digit,12,0,9.0e6,0.705,fixed,-0.14,0,0.01100,A,line-trace,0.0003,0.004,strong track in upper piece
TM-81927,8,0012,4-digit,12,0,9.0e6,0.730,fixed,-0.14,0,0.01099,A,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,9.0e6,0.775,fixed,-0.14,0,0.01350,C,band-strand,0.0008,0.006,knee band; continuity assignment
TM-81927,8,0012,4-digit,12,0,9.0e6,0.790,fixed,-0.14,0,0.01130,C,band-strand,0.0010,0.008,non-monotonic vs 0.775 row; band ambiguity dominates
TM-81927,8,0012,4-digit,12,0,9.0e6,0.818,fixed,-0.14,0,0.01730,A,marker-machine+shape,0.0003,0.004,diamond glyph confirmed in knee crop
TM-81927,8,0012,4-digit,12,0,9.0e6,0.826,fixed,-0.14,0,0.02350,C,band-strand,0.0010,0.006,series terminates near M 0.825-0.83; no diamond endpoint at 0.84
TM-81927,8,0012,4-digit,12,0,3.0e6,0.301,free,-0.14,0,0.00630,A,marker-machine+shape,0.0002,0.003,plus glyph confirmed visually at low-M tail
TM-81927,8,0012,4-digit,12,0,3.0e6,0.354,free,-0.14,0,0.00613,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.482,free,-0.14,0,0.00612,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.516,free,-0.14,0,0.00601,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.534,free,-0.14,0,0.00601,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.579,free,-0.14,0,0.00602,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.640,free,-0.14,0,0.00633,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.667,free,-0.14,0,0.00631,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.688,free,-0.14,0,0.00631,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.695,free,-0.14,0,0.00625,A,marker-machine,0.0002,0.003,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.735,free,-0.14,0,0.00650,B,line-trace,0.0003,0.004,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.757,free,-0.14,0,0.00675,B,line-trace,0.0003,0.004,onset of gentle rise
TM-81927,8,0012,4-digit,12,0,3.0e6,0.774,free,-0.14,0,0.00728,B,line-trace,0.0004,0.005,
TM-81927,8,0012,4-digit,12,0,3.0e6,0.785,free,-0.14,0,0.00890,A,marker-machine,0.0004,0.004,wide plus-profile marker n34
TM-81927,8,0012,4-digit,12,0,3.0e6,0.791,free,-0.14,0,0.00916,A,marker-machine,0.0004,0.004,wide plus-profile marker maxlen56
TM-81927,8,0012,4-digit,12,0,3.0e6,0.840,free,-0.14,0,0.02960,A,marker-machine+shape,0.0002,0.003,plus endpoint confirmed visually
```

## C. ferri-2309.csv (45 points, NACA WR L-143 Figure 33 Continued, CALIBRATION)

```csv
# Re: Guidonia open-jet tunnel held Re approximately constant at 0.34-0.42e6 across all Mach (report p.13/15); nominal mid-band 3.8e5 recorded per point. Corrected 2026-08-23; see docs/protocol-deviations.md D10.
report,figure,airfoil,family,tc_percent,camber,Re,mach,transition,alpha_deg,CL_nominal,CD,quality_tier,method,uncertainty_cd,uncertainty_M,notes
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.400,free,"-1,0",,0.0116,A,agent-QC label-anchored,0.0005,0.004,CORRECTED 2026-08-23: replaces first manual read which was 5-8 counts high (glyph tops read instead of centers)
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.500,free,"-1,0",,0.0116,A,agent-QC label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.600,free,"-1,0",,0.0115,A,agent-QC label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.650,free,"-1,0",,0.0121,A,agent-QC label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.700,free,"-1,0",,0.0120,A,agent-QC label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.720,free,"-1,0",,0.0136,B,agent-QC label-anchored,0.0008,0.004,marker printed small/faint; confirmed in three crops
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.750,free,"-1,0",,0.0158,A,agent-QC label-anchored,0.0005,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.780,free,"-1,0",,0.0170,A,agent-QC label-anchored,0.0005,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.800,free,"-1,0",,0.0185,A,agent-QC label-anchored,0.0005,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.822,free,"-1,0",,0.0232,A,agent-QC label-anchored,0.0007,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.845,free,"-1,0",,0.0296,A,agent-QC label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.869,free,"-1,0",,0.0342,A,agent-QC label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.897,free,"-1,0",,0.0485,B,agent-QC label-anchored,0.0009,0.003,steep region; M uncertainty dominates
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.920,free,"-1,0",,0.0661,B,agent-QC label-anchored,0.0008,0.004,congested cluster; glyph confirmed at 16x
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.941,free,"-1,0",,0.0742,A,agent-QC label-anchored,0.0008,0.004,endpoint; the previously reported 0.078 endpoint was the alpha=1 square glyph
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.400,free,1,,0.0141,B,agent label-anchored,0.0006,0.004,overlaps alpha=-2 triangle through plateau; center from box edges
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.501,free,1,,0.0140,B,agent label-anchored,0.0005,0.004,overlaps alpha=-2 triangle
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.601,free,1,,0.0140,B,agent label-anchored,0.0005,0.004,overlaps alpha=-2 triangle
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.650,free,1,,0.0139,A,agent label-anchored,0.0004,0.004,clean glyph
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.700,free,1,,0.0149,A,agent label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.750,free,1,,0.0169,A,agent label-anchored,0.0005,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.780,free,1,,0.0191,A,agent label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.800,free,1,,0.0209,A,agent label-anchored,0.0004,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.820,free,1,,0.0242,A,agent label-anchored,0.0005,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.848,free,1,,0.0330,A,agent label-anchored,0.0005,0.004,alpha=-2 triangle directly above
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.870,free,1,,0.0364,A,agent label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.898,free,1,,0.0539,A,agent label-anchored,0.0006,0.004,verified square at 20x zoom
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.919,free,1,,0.0719,B,agent label-anchored,0.0007,0.004,verified at 24x; near-glyphs excluded by shape check
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.939,free,1,,0.0796,B,agent label-anchored,0.0008,0.004,endpoint in dense cluster; separable from diamond and circle endpoints
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.400,free,2,,0.0179,B,agent label-anchored,0.0007,0.004,circle atop fused pair with alpha=-3 inverted triangle
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.500,free,2,,0.0175,C,agent label-anchored,0.0008,0.004,almost fully overlapped with alpha=-3; center partly inferred
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.600,free,2,,0.0178,B,agent label-anchored,0.0006,0.004,inverted triangle just below
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.650,free,2,,0.0196,A,agent label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.700,free,2,,0.0220,A,agent label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.720,free,2,,0.0239,A,agent label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.750,free,2,,0.0250,A,agent label-anchored,0.0007,0.004,alpha=3 curve line crosses marker
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.765,free,2,,0.0249,A,agent label-anchored,0.0007,0.004,local flat spot in the rise
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.780,free,2,,0.0260,A,agent label-anchored,0.0006,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.800,free,2,,0.0263,B,agent label-anchored,0.0007,0.004,partially fused with alpha=-2 triangle
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.820,free,2,,0.0300,B,agent label-anchored,0.0008,0.004,alpha=-2 triangle fused just below
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.850,free,2,,0.0401,C,agent label-anchored,0.0012,0.004,marker swallowed by alpha=-3 overlap; from lower glyph plus curve line
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.870,free,2,,0.0461,A,agent label-anchored,0.0007,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.899,free,2,,0.0639,A,agent label-anchored,0.0008,0.004,
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.920,free,2,,0.0792,B,agent label-anchored,0.0009,0.004,round glyph verified at zoom
WR-L143,33cont,2309,4-digit,9,2,3.8e5,0.941,free,2,,0.0877,A,agent label-anchored,0.0008,0.004,endpoint; clean circle between alpha=3 and alpha=4 flags
```

## D. ferri-cl.csv (60 lift points, NACA WR L-143 Figure 33 first sheet)

```csv
# CL(M) read from WR L-143 Fig 33 first sheet (scan p.80), NACA 2309, Guidonia, Re ~0.38e6.
# Read 2026-08-23 against printed axis labels (CL 0.1 per label / 0.05 per gridline; M 0.1 per label / 0.05 per gridline).
# u_CL: 0.010 for M <= 0.80, 0.012-0.015 at M 0.82, 0.020-0.030 from M 0.85 through the lift-break dive.
# Curve identities from the alpha label column on the figure: -1 = diamond, 0 = up-triangle, 1 = down-triangle, 2 = right-flag.
alpha,M,CL,u_CL
-1,0.40,0.095,0.010
-1,0.50,0.098,0.010
-1,0.60,0.105,0.010
-1,0.65,0.112,0.010
-1,0.70,0.122,0.010
-1,0.72,0.126,0.010
-1,0.75,0.133,0.010
-1,0.78,0.136,0.010
-1,0.80,0.132,0.010
-1,0.82,0.122,0.012
-1,0.85,0.078,0.020
-1,0.87,0.010,0.025
-1,0.90,-0.065,0.025
-1,0.92,-0.100,0.030
-1,0.94,-0.085,0.030
0,0.40,0.195,0.010
0,0.50,0.199,0.010
0,0.60,0.209,0.010
0,0.65,0.219,0.010
0,0.70,0.236,0.010
0,0.72,0.242,0.010
0,0.75,0.248,0.010
0,0.78,0.254,0.010
0,0.80,0.250,0.010
0,0.82,0.220,0.015
0,0.85,0.145,0.020
0,0.87,0.075,0.025
0,0.90,-0.070,0.025
0,0.92,-0.075,0.030
0,0.94,-0.050,0.030
1,0.40,0.285,0.010
1,0.50,0.290,0.010
1,0.60,0.300,0.010
1,0.65,0.307,0.010
1,0.70,0.320,0.010
1,0.72,0.328,0.010
1,0.75,0.340,0.010
1,0.78,0.350,0.010
1,0.80,0.348,0.010
1,0.82,0.332,0.015
1,0.85,0.275,0.020
1,0.87,0.215,0.025
1,0.90,0.050,0.030
1,0.92,0.020,0.030
1,0.94,0.040,0.030
2,0.40,0.390,0.010
2,0.50,0.395,0.010
2,0.60,0.405,0.010
2,0.65,0.415,0.010
2,0.70,0.430,0.010
2,0.72,0.440,0.010
2,0.75,0.455,0.010
2,0.78,0.465,0.010
2,0.80,0.463,0.010
2,0.82,0.448,0.015
2,0.85,0.380,0.020
2,0.87,0.320,0.025
2,0.90,0.150,0.030
2,0.92,0.130,0.030
2,0.94,0.185,0.030
```

## E. ferri-qc-sample.csv (the independent double-read sample)

```csv
sweep_id,mach,primary_cd,qc_cd,delta_counts
F33-a1,0.400,0.0141,0.0141,0.0
F33-a1,0.800,0.0209,0.0210,1.0
F33-a1,0.919,0.0719,0.0720,1.0
F33-a1,0.939,0.0796,0.0794,2.0
F33-a2,0.500,0.0175,0.0175,0.0
F33-a2,0.820,0.0300,0.0300,0.0
F33-a2,0.850,0.0401,0.0405,4.0
F33-a2,0.941,0.0877,0.0876,1.0
```

## F. ferri-re.csv (the Guidonia tunnel operating curve)

```csv
M,Re_million
0.40,0.38
0.94,0.38
```

## G. The NeuralFoil n_crit sweep used for the tunnel-turbulence calibration

NACA 0012, alpha -0.14 deg, Re 3.0e6, free transition, computed on the pinned Python path.

```csv
n_crit,CD
3,0.00684
4,0.00644
5,0.00614
6,0.00587
7,0.00561
8,0.00536
9,0.00512
10,0.00489
11,0.00467
```

## H. The Ferri gate matrix (NACA 2309, alpha 0, measured CD 0.0116)

```csv
Re,n_crit,CD_predicted,gap_counts
0.34e6,4,0.00716,44.4
0.34e6,6,0.00677,48.3
0.34e6,9,0.00676,48.4
0.38e6,4,0.00703,45.7
0.38e6,6,0.00648,51.2
0.38e6,9,0.00644,51.6
0.42e6,4,0.00696,46.4
0.42e6,6,0.00624,53.6
0.42e6,9,0.00617,54.3
```

## I. The pilot recalibration result table

```csv
model,fold_alpha0,fold_alpha1,fold_alpha2,mean_MAE_counts,parameters
exact_stock_pipeline_ASB_4.2.10,154.7,303.1,314.9,257.6,shipped
null_k_times_80_quartic,77.8,43.2,79.1,66.7,k=0.122 (effective constant 9.8)
F1_selected,58.3,32.9,57.8,49.7,A=1.314 b=2.607
```

Per-sweep inputs: baselines 0.01170 / 0.01403 / 0.01770; M_crit 0.6871 / 0.6542 / 0.6246; transonic point counts 9 / 8 / 11. No-harm onset-window MAE, stock versus refit: 10.5 to 10.0, 5.1 to 4.4, 18.7 to 18.1 counts.

## J. Measured drag-rise onsets (computed from Appendix C)

```csv
sweep,predicted_Mcrit,measured_onset_plus5ct,gap,measured_Mdd_plus20ct,predicted_Mdd
alpha2,0.6246,0.611,0.014,0.652,0.693
alpha1,0.6542,0.682,0.028,0.728,0.722
alpha0,0.6871,0.703,0.015,0.721,0.755
```

---

*End of document. Every number above is verified against the source reports, the installed code, or an executed run. Nothing is estimated.*
