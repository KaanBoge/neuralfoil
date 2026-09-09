# Methods and reproducibility

## Two execution paths

The browser starts at `index.html` and `nfb.js` using existing assets. Research Python source is retained under `code/research/`. Do not silently substitute predictions or preprocessing between them. “New NeuralFoil” and “NeuralFoil B” in the older interface refer to that release, not a newly installed research model.

## Input contract

X62 has a fixed column order: 24 baseline/operating descriptors, 20 transition-sensitivity descriptors, and 18 Kulfan coefficients (eight upper, eight lower, leading-edge weight and trailing-edge thickness).

For each alternative `ncrit=5,7,11,13` relative to 9, sensitivity features contain log drag ratio, lift difference, confidence difference and two transition-location differences. These are computed model sensitivities, not measured tunnel turbulence. Nominal inference uses Mach zero and free transition. Historical generation used NeuralFoil 0.3.3 and AeroSandbox 4.2.10 with the original coordinate-to-Kulfan convention.

Native drag is rounded to six decimal places, lift to five, confidence and transition locations to four, and mean moment to five. Replacing them with unrounded predictions changes the input. Matching array width alone does not establish compatible feature order, normalization or precision.

## Core and strength

Let `b` denote mean8 drag and `y` measured drag. The bounded core learns `clip((y-b)/b, -0.5, 1)`. The regularized reference uses histogram absolute-error regression: 400 stages, at most 15 leaves, minimum leaf size 120, learning rate 0.035, L2 regularization 5, seed 824, no early stopping. Training weights combine row and source/identity balance, multiplied by `b`.

The core output lies between `0.5*b` and `2*b`. Half strength is `b + 0.5*(core-b)`, not half the learned policy output. The learned transfer reference chooses strength from numerical risk descriptors using training-only out-of-fold predictions. Airfoil names and measured test outcomes are not deployment features.

The inherited physical gate requires finite inputs, positive mean8 drag, `0 < Re <= 600000`, `abs(alpha) <= 12` degrees and thickness/chord between 0.05 and 0.20. Point corrections return mean8 outside the gate. Interval projection instead preserves its supplied baseline. Qualified procedures can add a separately declared numerical guard.

## Evaluation

Two five-fold identity assignments reuse the historical archive. Five source contexts purge both the held-out source and its identities from training. A final historical fit supplies exposed SG/W evaluations; its historical in-sample predictions are not held-out accuracy.

Proper-training and calibration roles must remain separate. Frozen phase boundaries and all prescribed adverse comparisons matter. The 31 reporting views overlap; repeated rows are not new measurements.

Interval coverage, added-loss control and tree enclosures answer different questions. Sampling assumptions remain necessary, and adaptive reuse prevents interpreting these experiments as fresh certification. Enclosures cover a specified ordered floating-point evaluator; they do not establish attainable extrema or a percentage reduction in measured error.

## Running archived source

The small public inference entrypoint is `code/research/model_development_20260907_risk_policy/portable/predictor.py`. Its API is `predict(artifact, X62, BASE_CD, all_model_CD, gate, label)`, returning `(CD, applied_strength)`. It performs no filesystem access or sklearn/pickle loading.

Supply finite numerical X62 of shape `(n,62)`, positive mean8 `BASE_CD` of shape `(n,)`, positive native drag of shape `(n,8)` in `xxsmall/xsmall/small/medium/large/xlarge/xxlarge/xxxlarge` order, and a mandatory Boolean gate of shape `(n,)`. The caller must construct the physical gate and correct feature contract; the predictor does not derive them from raw coordinates or verify that the supplied baseline equals the arithmetic mean. Invalid inputs are rejected even when their gate is false.

Select `risk_transfer`, `unpenalized_transfer` or `risk_group` explicitly. The example chooses `unpenalized_transfer`; the function's historical default is `risk_transfer`, not a universal recommendation. This older feature-level interface is distinct from later qualified H/KL procedures.

1. Identify one procedure. Read its imports, argument parser and expected input identities before execution.
2. Obtain authorization for its actual inputs and artifacts; paths and hashes do not supply them.
3. Use an isolated compatible environment. Review path adapters separately rather than disabling integrity checks.
4. Start with an explicitly named synthetic test. Archived integration tests can require real artifacts; broad discovery is not a safe substitute.
5. Preserve versions, roles, warnings, failures and complete outputs in any reconstruction.

This is not one-command reproduction of the private study. Synthetic checks, saved-file integrity, numerical replay and new experimental validation establish different things.
