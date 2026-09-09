# NeuralFoil Studio and Research Code

### Airfoil prediction. Measured drag discrepancies. Explicit limits.

**An airfoil analysis and research-code project by [Kaan Boge](https://github.com/KaanBoge).** This repository combines the existing browser Studio with a source archive for measurement-informed drag correction, calibration and numerical verification. It is separate from upstream NeuralFoil.

**[Research overview](https://kaanboge.github.io/neuralfoil/research.html)** · **[Open the Studio](https://kaanboge.github.io/neuralfoil/)** · **[Methods](docs/METHODS.md)** · **[Data and access](docs/DATA.md)** · **[Current scope](docs/STATUS.md)**

**[Browse the source guide](code/README.md)** · [Original code: MIT](LICENSE) · [License scope](LICENSING.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

> The browser application and newer research procedures are different implementations. Adding research source does **not** install the newer correction in the website. The current manuscript, its figures and private reproduction packages are not part of this release.

**About the name:** NeuralFoil B is the existing browser wrapper's name: mean-of-eight native models, the legacy gated lift correction and empirical diagnostics. It is not an official upstream NeuralFoil version or the name of a newly installed research drag predictor. The [research page](https://kaanboge.github.io/neuralfoil/research.html) makes this distinction visible and provides a searchable [complete tracked-source catalog](code/source-catalog.json). The catalog measures published coverage, not ownership clearance or end-to-end reproducibility.

## Start here

| If you want to… | Start with |
|---|---|
| Explore the existing airfoil interface | [Browser Studio](https://kaanboge.github.io/neuralfoil/) |
| Read the research without the manuscript | [Research overview](https://kaanboge.github.io/neuralfoil/research.html) |
| Find runnable examples and archived source | [Source guide](code/README.md) |
| Understand correction and preprocessing | [Methods and reproducibility](docs/METHODS.md) |
| Identify required but unavailable inputs | [Data guide](docs/DATA.md) |
| Separate measured gains from guarantees | [Status](docs/STATUS.md) |
| Understand older website terminology | [Historical README](docs/LEGACY_STUDIO.md) |
| Propose a reproducible change | [Contributing](CONTRIBUTING.md) |

## What the research code does

The correction leaves NeuralFoil's neural-network weights unchanged. A separate shared model uses geometry, operating conditions and NeuralFoil-derived descriptors to correct drag. It starts from the mean of eight native model sizes; xlarge remains a separate comparison baseline.

The established learned-strength reference reduced historical drag mean absolute error by **20.47% and 19.69% relative to xlarge**, in two grouped assignments of the **same 8,371 observations and 93 conservative airfoil identities**. These are not independent experimental replications. Some rows, identities and external cases became worse, and all evaluation collections were adaptively reused.

The archive also covers half-strength controls, interval projection, added-loss calibration and conservative tree bounds. A tighter bound is not an equal percentage improvement in prediction. These are research procedures, not a universal replacement or flight-safety certificate. Their trees and hard gates do not preserve global differentiability.

## Run the existing site locally

With Python 3 installed, run from the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open [localhost:8000](http://localhost:8000). HTTP is needed for relative data fetches. This serves the existing application; it does not run the Python experiments.

## Try the source interface with artificial inputs

This example needs only Python and NumPy, not NeuralFoil, trained correction weights or measurements. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install numpy==2.3.5
.venv/bin/python -B examples/synthetic_policy.py
.venv/bin/python -B -m unittest discover -s tests -p test_public_smoke.py -v
```

The example and six targeted tests passed in Python 3.12.14 with NumPy 2.3.5. The artificial example returns CD `[0.0125, 0.02]`, applied strength `[0.5, 0.0]`, and an exact false-gate fallback. This demonstrates the interface, **not aerodynamic accuracy**. The example constructs constant parameters; no trained model is released by that demonstration. Environment creation and installation commands are setup instructions, not a claim of a fresh-install reproduction test.

## Repository structure

```text
index.html, nfb.js       Existing browser application
research.html/.css/.js   Research overview and searchable source catalog
nfweights/              Existing model assets and references
study/                  Earlier website and study material
code/research/          Original reviewed research archive
code/supplement/        Source-only completeness additions; see its manifest
examples/, tests/       Explicitly synthetic public examples and smoke tests
docs/                   Technical guides and historical README
```

The research tree is a source archive, not a ready-made Python package. Some scripts retain local paths and authenticated-input assumptions. Full reconstruction requires authorized inputs, compatible dependencies and reviewed path adapters. Do not assume broad test discovery across archived experiments is synthetic or self-contained.

The [source guide](code/README.md) explains completeness, generic utility additions, historical failures and excluded manuscript content. The source catalog can be regenerated from the Git index with `python -B tools/build_source_catalog.py --repo .`; after staging it, `python -B tools/verify_source_catalog.py --repo .` verifies the complete tracked-source set and its hashes. This is a repository-integrity check, not an accuracy evaluation.

## Attribution and reuse

Original project code and new associated technical documentation are available under the **[MIT License](LICENSE)**, copyright (c) 2026 Kaan Boge. Commercial use and integration are permitted subject to its notice requirements. The [scope guide](LICENSING.md) preserves third-party and historical data/document terms. This is not a blanket research-data license or a safety, universal-accuracy or real-time-performance guarantee.

[CITATION.cff](CITATION.cff) supplies software metadata; record the exact commit and procedure used. No DOI, journal acceptance or independent experimental confirmation is claimed.

Third-party software and data retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Repository visibility alone does not grant rights to measurement collections or recovered coordinates. Substantive generative-AI assistance supported implementation, analysis, testing and documentation; it was not limited to language editing.
