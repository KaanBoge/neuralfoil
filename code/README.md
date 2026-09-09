# Research source archive

This directory contains **694 Python source files**, with an individual original and published SHA-256 in [research-manifest.json](research-manifest.json). It includes algorithms, historical experiments, tests, verification and execution helpers, not just successful experiments. Inclusion is not model promotion.

## Useful entry points

| Purpose | Source |
|---|---|
| NumPy-only feature-level inference | [Portable predictor](research/model_development_20260907_risk_policy/portable/predictor.py) |
| Original capacity families | [Capacity models](research/model_development_20260907_frontier/capacity/capacity_models.py) |
| Controlled core variants | [Core models](research/model_development_20260907_cap_ablation/cap_models.py) |
| Learned strength mathematics | [Risk policy](research/model_development_20260907_risk_policy/risk_policy.py) |
| Earlier interval projection | [Selective correction](research/model_development_20260907_selective/selective.py) |
| Exact feature-name lists and general exporter | [Portable models](research/model_development_20260907_search/portable/portable_models.py) |
| Later qualified procedures and numerical verification | [Renewed research](research/submission_revision_20260908/work/renewed_research/) |

The dates and original relative paths distinguish historical procedures. They are not package versions. The later eight-tree code is a separate numerical-bound experiment, not an eight-tree accuracy improvement.

## First checks

From the repository root in an isolated Python environment:

```sh
python -m pip install -r requirements-smoke.txt
python -B tools/verify_source_archive.py
python -B examples/synthetic_policy.py
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

These commands check source integrity and explicitly artificial inputs. They do not load trained weights or measurement records and do not measure aerodynamic accuracy. The observed local environment was Python 3.12.14 and NumPy 2.3.5. The eight targeted checks passed. This is not a fresh installation or cross-platform replay result.

Only the inference/example path needs NumPy. Selected fitting procedures additionally need scikit-learn and SciPy; historical data pipelines may need pandas, NeuralFoil and AeroSandbox. Read each module before selecting a runtime. The full private environment is not supplied by `requirements-smoke.txt`.

## Preservation and exclusions

Most files are byte-identical to the original research sources. Eleven public copies replace an absolute author-home prefix with the literal `/PATH_TO_YOUR_HOME`. Their original and published hashes differ and both are recorded. This is a privacy placeholder, **not a portability fix**; configure paths and dependencies explicitly before running those archived helpers. Frozen references inside historical code still refer to original artifacts, not silently redefined public copies.

The source selection excludes manuscript builders, paper-only review/assembly helpers and cached third-party web pages. No new measured rows, recovered geometry, trained model files, pickle/NPZ replay inputs, private archives or paper figures accompany this source tree. Some source code deliberately names those absent inputs or output fields. Naming a file does not redistribute it or grant access.

Do not run broad test discovery inside `research/`: some historical tests load original measurements, fit estimators or write artifacts. Start with the named synthetic suite above. See [data access](../docs/DATA.md), [methods](../docs/METHODS.md) and [licensing](../LICENSING.md).
