# Status and scope

## Existing website

The Studio is the existing browser application. Its older “New NeuralFoil” terminology is preserved in the [historical README](LEGACY_STUDIO.md). New Python source is not silently installed into that interface. Publication does not establish browser parity with newer procedures.

## Research archive

The source covers correction families, assessment infrastructure, selective intervention, numerical bounds and implementation checks. Original relative paths distinguish experiments and successors. Presence of a file does not mean its experiment passed or that all its inputs are public.

The established learned-strength reference gives 20.47% and 19.69% historical drag MAE reduction against xlarge on two partitions of the same 8,371-row, 93-identity archive. Half-core correction gives smaller gains and positive mean reductions across all 31 views against both native baselines, while still harming individual observations and identities.

Stronger conditional calibration and paired/four-tree bounds retain adverse external cases and fail the unchanged advancement criteria. A later sole-model eight-tree bound has no corresponding contextual recalibration or scored accuracy result. It is not an eight-tree prediction improvement.

## Limits

The work does not establish universal improvement, flight safety, improved lift/moment/stall or optimization derivatives from the drag correction, or independent confirmation from reused outcomes. Nor does it establish a new general conformal theorem, attained global optimum or portable bitwise equality in every runtime.

Local input reconstruction, numerical replay and runtime checks have specific environments and workloads. Source publication does not automatically reproduce those checks elsewhere. Preserve first failures and reviewed successors instead of describing uninterrupted success.

## Assistance and responsibility

Kaan Boge maintains the project. Substantive generative-AI assistance supported implementation, mathematical/numerical review, analysis, testing and documentation. It is not independent human peer review or an authorship attestation, and was not limited to language editing. Scientific interpretation and release decisions remain the maintainer's responsibility.

No journal acceptance, research DOI or blanket input-redistribution permission is claimed.
