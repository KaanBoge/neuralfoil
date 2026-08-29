# The Answer to the Research Question
## Complete results of the executed study, 2026-08-28

**The question:** Where does NeuralFoil disagree with wind-tunnel experiment; can its weakest layer, the transonic drag rise, be recalibrated to reduce error on data it has never seen; and can its self-reported confidence be turned into calibrated error bounds?

**The answer, in one paragraph:** NeuralFoil is a faithful surrogate whose subsonic predictions match independent wind-tunnel measurement to within one or two drag counts at matched conditions, and whose drag-rise onset prediction is verified here for the first time to about one hundredth in Mach. Its failures concentrate along three measured axes: low Reynolds number, both stall wings, and geometry far from the training heartland, plus one broad shape defect in the transonic drag-rise formula. The attempted three-parameter recalibration of that formula, selected honestly on calibration data, FAILED its pre-registered criteria on both held-out datasets: the simple functional family cannot span the drag rise from onset to deep transonic across thickness and camber, and a fit that helps in one regime harms the other. The confidence score broadly tracks error but has two measurable blindspots, and the registered conformal bound came out too wide to be useful and is declared uninformative. Every one of those negative clauses is a finding, established by a design that made it impossible to hide.

---

## PART 1. Where NeuralFoil disagrees with experiment (Phase A, executed)

**Subsonic accuracy at matched conditions is excellent.** Against Harris's 1981 measurements (the highest-quality conventional dataset per McCroskey), the fixed-transition sanity gates passed at 1.3 and 0.5 drag counts using the registered plateau-mean estimator. Against XFOIL itself, NeuralFoil reproduces its teacher to a median of 1.6 to 2.7 counts, so the residual gaps against experiment are facility and teacher physics, not surrogate error.

**Onset prediction is quantitatively trustworthy: the developers' claim is now verified.** Predicted drag-divergence Mach versus measured, on the clean calibration sweeps: errors of +0.003, +0.001, −0.012, +0.004, −0.012. On the spent holdouts, the stock M_dd = M_crit + 0.068 rule landed within 0.029 in Mach on average on BOTH holdout sets. The measured drag-rise onsets on Ferri's three sweeps also appear in exactly the order and position the Cp-based critical-Mach formula predicts.

**The magnitude of the drag rise is where the model fails, and the failure now has a measured shape.** The stock formula underpredicts the early drag creep by factors of 2 to 8 at M_crit + 0.05 and overpredicts by 1.4 to 4.4 by M_crit + 0.15 on constant-Reynolds sweeps; on the deep-transonic TN 3607 sweeps reaching M 0.90, the fitted stock-shape multiplier collapses to k about 0.03, meaning the shipped quartic is orders of magnitude too steep there. Too shallow early, too explosive late, on every dataset.

**The failure map at scale (312,795 conditions, all 1,655 UIUC airfoils, eight model sizes).** Ensemble spread across the eight shipped model sizes is a fabrication-free lower bound on error. It shows: at Re 50,000, 94 percent of conditions carry spread above 20 counts; the share falls monotonically to 4 percent at Re 10^8, so extrapolating down into transitional flow is dangerous while extrapolating up is nearly safe. Angle of attack shows a U with its floor at 1 to 3 degrees; by 16 degrees the median spread is 80 counts. Thickness shows a U with its floor at 9 to 12 percent. Within the practical envelope (Re 200k to 5M, alpha −4 to +10), 26 percent of conditions sit in the tight-agreement zone, 20 percent are unreliable; outside it, 45 percent are unreliable.

**Where the teacher itself gives up.** XFOIL failed to converge on 12 percent of a stratified sample; NeuralFoil answers there anyway, with internal disagreement 1.8 times higher than where XFOIL converges. "Always returns an answer" is most dangerous exactly where the teacher could not produce one.

**Transition handling is clean (a positive audit).** Tripping at the natural transition point reproduces the free solution within about 2 counts; trip location moves drag monotonically on 100 percent of the sample. The n_crit lever arm, 11.4 counts median across its plausible range, quantifies the invisible uncertainty every free-transition comparison inherits, and is why this study pinned per-facility values (8-ft TPT about 4.9; the two 1940s-50s tunnels about 6).

**Facility physics the audit had to untangle to get any of this right:** Harris's 9-million fixed series carries about 36 counts of trip overdrag (predicted by the literature, confirmed by the gate); Ferri's Guidonia data sit about 50 counts high at a constant Re of 0.38 million and entered as increments only; TN 3607's induction tunnel varies Reynolds with Mach, so its baseline had to be Reynolds-corrected (a declared amendment) or a false 6-to-11-count increment appears; its 64A012 section is non-monotonically low in the published figure itself and was excluded from gates.

## PART 2. Can the drag-rise layer be recalibrated? (Phase B, executed, one-shot spent)

**The definitive fit:** 17 calibration sweeps, 139 transonic points, six airfoils, thickness 4 to 12 percent, lift to 0.83, two sources, leave-one-source-out, four pre-registered candidate forms, uncertainty-aware and tier-weighted, on the pinned Python path against the machine-precision-verified reimplementation of the shipped layer (worst reproduction difference 6e-17).

**Selection:** F1, dCD = 7.71 (M − M_crit)^4.93, won leave-one-source-out at 89.7 counts against the null's 126.3. Two warnings were visible at selection time and are reported: the bootstrap interval on the amplitude spans four orders of magnitude (power-law ridge degeneracy), and the geometry-dependent form F3 saturated a declared parameter bound, meaning the candidate family itself was too small.

**The one-shot verdict (spent 2026-08-28, reported as it landed):**

| Criterion | Harris | TN 1546 subset |
|---|---|---|
| Drag-rise increment MAE, at least 30 percent below stock | stock 37.3 to model 66.4 counts, WORSE by 78 percent: **NOT MET** | stock 28.1 to model 25.5, better by only 9.3 percent: **NOT MET** |
| M_dd error halved | stock 0.029 to model 0.176: **NOT MET** | stock 0.028 to model 0.175: **NOT MET** |
| No-harm below M_crit | **PASS** (0.00 counts added, structural) | **PASS** |

**Why it failed, mechanistically.** The calibration set reaches deep transonic conditions (increments to 640 counts at M 0.90 in a choking-free open-jet tunnel); the holdout sweeps stop near onset (M 0.84 to 0.86, and near choking at 0.78 to 0.84). A single power law steep enough for the deep data (exponent about 4.9) is far too late-rising for near-onset data, so it loses to the stock shape exactly where the stock shape is least wrong. The earlier pilot's 81 percent improvement on one airfoil was real but regime-local; the family holdout did precisely the job it was registered for and caught the non-transfer.

**The honest conclusion for the paper:** the transonic drag rise of these families is not describable by any single two-or-three-parameter (M − M_crit) power law across thickness, camber, and Mach depth. The physically indicated repair, supported by TN 3607's own transonic-similarity figure, is a thickness-scaled similarity form, dCD proportional to (t/c)^(5/3) times a universal function of the similarity variable, which lies outside the pre-registered candidate family and is the concrete, data-backed future work. The proposal anticipated this outcome in writing: a negative Phase B result is a real and reportable finding.

## PART 3. Is the confidence score calibrated? (Phase C, executed)

**It is informative but not sufficient.** Median ensemble spread falls from 158 counts in the lowest-confidence bin to about 7 in the highest, so the score carries real signal. But it saturates at the top (the 0.95-to-1.0 bin, holding half of all conditions, is slightly worse than the bin below), and 7.4 percent of all atlas conditions (23,089) combine confidence above 0.90 with spread above 50 counts, concentrated at thick sections, low Reynolds, and high alpha. The lift analogue is 2.3 percent. This is a second, empirically discovered blindspot beyond the registered structural one (the score never sees the Mach number and cannot flag transonic error by construction).

**The registered conformal bound is declared UNINFORMATIVE.** Computed exactly as pre-registered from calibration increments, it came out at 567 counts; holdout coverage was 100 percent of 51 points, outside the exact binomial window around 90 percent. A bound that wide covers everything and helps no one; the registered procedure requires saying so, and the cause is the same heterogeneity that sank the recalibration: calibration and holdout points are not exchangeable across regimes this different.

## PART 4. What remains outside this study's coverage (stated, not hidden)

Pitching moment, post-stall behavior, and three-dimensional effects are outside the pre-registered scope. Where all eight model sizes agree AND XFOIL converges, shared teacher bias against reality remains bounded only by the experimental comparisons, which cover conventional families at Re 0.4 to 9 million and M up to 0.94. The full TN 1546 family beyond the declared 8-airfoil subset, the supercritical boundary probes (TP-2890, RAE 2822), and the cross-facility checks (TM 1240, TN 1813) remain unextracted. The M_crit decomposition refit and independent-reader QC of the TN 3607 and TN 1546 single-read extractions are pending. The A2 cubic M_dd rule is biased early on creep-heavy sweeps (quantified to −0.114 against the source authors' own fairing); it was applied identically to both models, so comparisons are fair, but absolute M_dd values from it carry that bias.

## PART 5. The deliverables on disk

Calibration: tn3607-sweeps.csv (242 pts), tn3607-fig17.csv (87 pts), tn3607-ordinates*.csv (exact geometry), ferri-2309.csv (45 pts), ferri-cl.csv. Holdout: tn1546-sweeps.csv (133 pts kept, 7 excluded by the declared quality rule), tn1546-cl.csv, tn1546_geom.npy (exact geometry). Harris: harris-fig8.csv (47 pts). Audit: atlas-out/ (312,795 conditions), atlas-summary.csv, xfoil-vs-nf.csv. Machinery: transonic_patch.py (verified 6e-17), fit_definitive.py, score_holdout.py, selected-model.json, holdout-scores.json, phaseA-battery.csv. Protocol: protocol-deviations-additions.md (A2b, A13-A15, D11-D12) continuing the log in LUMIERE-MASTER-HANDOFF.md Part 6. The one-shot is spent and its outputs are frozen; re-running it on this data would be meaningless by design.

## PART 6. Post-hoc exploration (2026-08-29, calibration data only, labeled as such)

The negative Phase B result pointed at transonic-similarity thickness scaling as the indicated repair. Tested exploratorily under the same leave-one-source-out protocol on the same 17 calibration sweeps: the von Karman scaling form improves cross-validated error only marginally (86.0 against F1's 89.7 counts), and adding a lift-squared term overfits outright (in-fit 71.9 but cross-validated 153.3). Residuals concentrate on the thickest section and the most cambered sweeps, exactly where shock-induced separation is strongest. The conclusion sharpens the paper's final claim: the transonic drag rise of these families resists every simple closed-form correction tried, five candidate families in total, because the missing physics (shock strength coupling to separation across geometry) is not expressible as any low-parameter function of (M, M_crit, t/c, CL). The fix for this layer is therefore not a constant retune at all. It is Mach-aware training data, which is the final rung of the future-work ladder and a different study. These numbers are model development, not validation; confirmatory testing of any future form requires data the spent one-shot never touched (the 16 unextracted TN 1546 airfoils, Gothert TM 1240, or the boundary probes).

## PART 7. The final sweep: every remaining testable surface, probed (2026-08-29)

Executed to close the directive "find every inaccuracy": four systematic probes over surfaces no earlier phase had touched, plus the first-ever scoring of the lift-compressibility layer against experiment.

**Hard-wrongs scan: CLEAN.** 2,160 conditions (60 airfoils, alpha −25 to +30, Re 50k to 20M): zero non-positive drags, zero |CL| > 4, zero transition locations or confidence values out of bounds, zero NaN. Minimum CD seen 0.00351. Degenerate geometries (near-zero-thickness plate, wide-open trailing edge) raise a loud TypeError instead of returning silent garbage, which is correct behavior. NeuralFoil never returns a physically impossible number in this scan; its inaccuracies are all of degree, not of kind.

**Smoothness: CLEAN.** Finite-difference kink scan across alpha (0.02-degree steps) and Reynolds (200 log steps): worst second-difference 0.092 counts in alpha and 0.020 in Re, far below the one-count level an optimizer would feel. The surrogate is safely smooth for gradient-based design, which is its main selling point.

**Geometry-input noise floor: a real, user-facing inaccuracy source.** Scan-level coordinate noise (sigma 2e-4 chord, the level a digitized or scanned airfoil carries) produces a median 0.4-count CD jitter, p90 1.1, but a worst case of 11.1 counts. Anyone feeding scanned coordinates inherits this floor. Mitigation is on the user side: smooth or refit coordinates (e.g. a CST fit) before querying.

**Moment coefficient: proportionally the least certain output.** Ensemble spread across the eight model sizes on CM: median 0.0035, p90 0.0140, max 0.080. Against a typical cambered-airfoil CM of 0.05 to 0.10, the p90 spread is about 18 percent of the quantity itself, roughly an order of magnitude worse in relative terms than subsonic drag. No measured moment data was extracted in this study, so CM remains ensemble-bounded only.

## PART 8. The lift-compressibility layer: audited for the first time, and two fix candidates honestly rejected (2026-08-29)

**The audit (120 measured lift points, never before used for this).** Subcritically the layer is adequate where the core model is: TN 1546 subset CL MAE 0.036 (digitization noise 0.01 to 0.02), with a thickness-growing bias reaching +0.07 on the 15-percent section, consistent with the thickness-U from the atlas. On Ferri's Re 0.38M data the subcritical MAE grows from 0.021 at alpha −1 to 0.143 at +2, well above noise: at this low Reynolds number the core model's lift level itself is off, before compressibility does anything.

**The discovered defect in the layer.** Measured lift at alpha +1 and +2 is still rising 19 to 23 percent at M 0.78 while the pipeline already predicts it falling 19 to 32 percent. The mechanism: the shipped buffet cut starts at mach_dd + 0.04 and therefore sweeps strongly with alpha (0.734 at +2, 0.805 at 0), while the measured breaks sit near M 0.78 to 0.85 at every alpha. The lift break inherits the alpha-dependence of drag divergence; measurement says the two events decouple.

**Fix candidate 1, a shifted onset (one parameter): REJECTED.** Leave-one-alpha-out on Ferri: 0.116 to 0.114 CL MAE (+2 percent, negligible), break-region MAE unchanged at 0.178, and the fitted shift moves the onset EARLIER, trading shape error for level error. Applied unchanged to the independent TN 1546 source it makes things worse (0.036 to 0.046). Rejected on transfer failure.

**Fix candidate 2, an alpha-detached onset tied to the reference-alpha mach_dd (one parameter): REJECTED.** Cross-validated MAE 0.116 to 0.119 (worse), break region unchanged, TN 1546 flat (0.036 to 0.035). The candidate encodes the measured alpha-independence and still buys nothing, because the dominant Ferri error is the low-Reynolds lift level in the core model, which no compressibility-layer parameter can reach.

**Verdict, matching the drag layer exactly.** The compressible-lift defect is real, measured, and not repairable by low-parameter retuning of the analytic layer. Both discovered defects (drag-rise shape, lift-break timing) point to the same repair, Mach-aware training data, which is retraining, not post-processing.

## PART 9. The complete inaccuracy registry (everything found, with fix status)

| # | Inaccuracy | Measured size | Fix status |
|---|---|---|---|
| 1 | Transonic drag-rise magnitude shape | 2-8x under early, 1.4-4.4x over late, ~30x too steep deep | Five closed forms + similarity scaling all FAIL holdout or cross-validation. Unfixable at layer level; needs Mach-aware retraining |
| 2 | Drag-divergence onset | 0.029 avg Mach error | No fix needed (verified good); recalibration attempt made it worse and was rejected by the registered one-shot |
| 3 | Low-Reynolds regime | Re 50k: 94% of conditions spread > 20 counts | Not post-processable. Mitigation: envelope guard + ensemble spread as bound |
| 4 | High alpha | median spread 80 counts at 16 deg | Same |
| 5 | Thickness extremes | U-shaped, floor at 9-12% t/c | Same |
| 6 | Answers where XFOIL diverges | 12% of sample, 1.8x spread there | Mitigation: ensemble spread flags it |
| 7 | Confidence never sees Mach (structural) | cannot flag transonic error by construction | Unfixable without retraining; use external Mach check |
| 8 | Confidence blindspot at thick/low-Re/high-alpha | 7.4% of atlas: conf > 0.90 yet spread > 50 counts | Mitigation: ensemble spread, not confidence, as the trust signal |
| 9 | Registered conformal bound | 567 counts, uninformative | Cause is regime heterogeneity; no fix with current data |
| 10 | Lift-break alpha-dependence | pred falls 19-32% where meas rises 19-23% (M 0.78, alpha +1/+2) | Two one-parameter candidates REJECTED (this study); needs retraining |
| 11 | Subcritical lift level at low Re | CL MAE to 0.143 at Re 0.38M, alpha +2 | Core-model error; unreachable from any post-processing layer |
| 12 | CL thickness bias (16-series) | signed +0.03 to +0.07 on thick sections | Consistent with #5; same mitigation |
| 13 | Geometry-input noise floor | median 0.4, max 11.1 counts at scan-level noise | User-side fix: smooth/refit coordinates before querying |
| 14 | CM relative uncertainty | p90 ensemble spread 18% of typical CM | Unvalidated vs experiment (out of scope); ensemble-bounded only |
| 15 | Positive audits for balance | hard-wrongs 0/2,160; smoothness 0.09 counts; transition clean; subsonic drag 1.3/0.5 counts | No fix needed |

**What "fixed" honestly means at the end of this study.** Every inaccuracy that could be found with the data obtainable on this machine has been found, measured, and bounded. Every one that admitted a testable layer-level fix got one built and scored under a protocol that could say no, and it said no every time, which is itself the paper's central result: the analytic compressibility layers of NeuralFoil cannot be repaired by low-parameter recalibration, because their errors are entangled with core-model error (low Re, lift level) or with physics no closed form in (M, M_crit, t/c, CL) expresses (shock-separation coupling). The working fix delivered instead is the bounded-tool package: the operating-envelope map, the ensemble-spread error bound (fabrication-free, validated against 92 experimental points), the facility-convention corrections, and the machine-exact reimplementation (transonic_patch.py) into which any future retrained layer drops directly.
