# NeuralFoil

Home of the new NeuralFoil (NeuralFoil B), the Studio, and the completed experimental validation study.

- [Open the site](https://kaanboge.github.io/neuralfoil/): lands on the New NeuralFoil tab
- [Browse the study files](study/): data, docs, tools, and the final answer document at `study/data/research-answer.md`

## The new NeuralFoil

The 2026 validation study measured NeuralFoil 0.3.3 against wind-tunnel experiment
(four NACA/NASA wind-tunnel reports, more than 600 digitized measured points, a
312,795-condition atlas across all eight model sizes), attempted to repair every
defect it found, and kept
only what survived held-out testing. The result is not a retrained model; it is the
same eight shipped networks with a validated trust layer around them:

- The core prediction is the mean of all eight model sizes, selected on measured
  data (ties the classic xlarge on Harris, 21 percent better drag on TN 1546,
  slightly better lift).
- Every force and moment coefficient carries its 8-network disagreement band, a
  fabrication-free measured lower-bound indicator of error. No coverage guarantee
  is claimed, because the study's registered conformal bound was honestly
  uninformative.
- A verdict engine checks every query against the measured failure map and says in
  words when a number should not be trusted, including Mach effects and the two
  confidence blindspots the classic score cannot see.
- The five transonic recalibrations and two lift-break repairs that FAILED holdout
  are documented on the New vs Classic tab and are not shipped. That honesty is the
  point of the release.

The in-browser port is self-tested on load against 40 Python reference runs
(machine precision, see `nfweights/ref.json`). Everything that was on this site
before the release is still here, unchanged, on the other tabs.
