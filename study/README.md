# NeuralFoil Experimental Audit and Recalibration Study

Working repository for the study "From Black Box to Bounded Tool: An Experimental Audit, Recalibration, and Uncertainty Calibration of the NeuralFoil Aerodynamic Surrogate" (Lumiere research program, 2026).

This folder exists for two reasons: durable versioned storage of the study's data and tools, and a public, verifiable timestamp for the pre-registered study design. The commit history of this repository is the audit trail: the Methods and pre-registration in `docs/` predate the definitive calibration fit, and any change to them after this commit must appear as a dated protocol deviation, never as a silent edit.

## Contents

- `docs/` : the study documents. `methods-section.md` holds the frozen 10-step Methods including the pre-registration box (calibration and holdout split, one-shot rule, success criteria, no-harm check). `protocol-deviations.md` is the running dated log of every deviation from the frozen design, with rationale.
- `data/` : extracted experimental datasets with full provenance columns. `harris-fig8.csv` (NACA 0012, NASA TM-81927 Fig. 8, 47 points, HOLDOUT: never used in fitting). `ferri-2309.csv` (NACA 2309, NACA WR L-143 / ACR L5E21 Fig. 33, three sweeps, calibration source, corrected 2026-08-23 after independent QC). `data-phase-report.md` documents extraction methods, sanity-gate results, and the machinery-validation pilot. `results-view.html` is a self-contained visual summary.
- `tools/` : the extraction pipeline. `harness.html` (pdf.js renderer with headless save endpoint), `plotscan.ps1` / `rowband.ps1` (machine gridline detection), `trace.ps1` / `cluster.ps1` / `paths.ps1` (ink-run tracing, marker clustering, curve following), `gen_dataset.py` (pinned-Python reproduction path).
- `evidence/` : the rendered scan crops that every extracted value was read from, so any point can be re-checked against the original figure.

## Source reports (all free, NASA NTRS)

Harris NASA TM-81927 (19810014503), Ferri NACA WR L-143 / ACR L5E21 (19930092764), NACA TN 3607 (19930084305), NACA TN 1546 (19930082349), McCroskey NASA TM-100019 (19880002254), NACA TR-824 (19930090976), NASA TP-2890 (19890008197), NACA TN 1813 (19930082487), NACA TM 1240 (19930090916). The digitized values in `data/` derive from these public-domain US government works.

## License

Data (`data/*.csv`): CC-BY 4.0. Code (`tools/`): MIT. Documents: all rights reserved by the author (Kaan Boge) pending journal submission.

## Final status (2026-08-29)

The study is complete. The definitive answer document, including the honest negative
Phase B result, the Phase C conformal verdict, the final probe sweep and the complete
15-entry inaccuracy registry, is `data/research-answer.md`. The one-shot holdout was
spent on 2026-08-28 and its outputs (`data/holdout-scores.json`) are frozen. The site
now ships the study's product as the New NeuralFoil tab: the same eight networks with
the measured trust map, disagreement bands, and verdicts around them. `data/ensemble-eval.json`
and `data/ensemble-eval-tight.json` record how the new mean-of-8 core was selected on
measured data. Nothing from the earlier study materials was removed.
