# Source publication boundary — September 9, 2026

The expanded release preserves the original 694-file Python research archive and adds 114 distinct supplementary Python sources. The supplement closes source-only gaps found in the local research workspace and supplied starter export, including numerical/replay helpers, generic document builders, package checks, historical finalizers and synthetic tests. Existing legacy study tools remain in their original public locations; exact duplicate copies were not added simply to inflate the file count.

## What “complete” means here

The repository-wide [source catalog](../code/source-catalog.json) inventories the eligible source files actually tracked in Git, with language, role, size and SHA-256. Its verifier detects missing, changed and extra tracked source files. It is not a claim that every historical archive was recovered, that every file is first-party, or that omitted data and trained models can be reconstructed from source alone. GitHub's language bar measures classified bytes, not code completeness or algorithmic contribution.

The original [research manifest](../code/research-manifest.json) remains unchanged. The new [supplement manifest](../code/supplement-manifest.json) records each original relative path, known duplicate aliases, original and published hashes, and any author-home placeholder replacement. Meaningfully different historical versions remain separately preserved. Incidental title/footer metadata is not the manuscript body; a filename containing “paper” does not by itself exclude generic code.

## Deliberate holds and exclusions

| Material | Disposition |
|---|---|
| Current manuscript, paper figures and private reproduction packages | Not published, as requested |
| 27 distinct source versions embedding substantive manuscript, captions or result narrative | Held unchanged; generic code-only counterparts are included where available |
| `home-parity.py`, `stub.f`, `stub2.f`, `stub3.f`, `stub4.f`, `stub5.f`, `stub6.f` from the XFOIL environment export | Authorship/provenance unresolved; not included or assigned this project's MIT license |
| Three XFOIL Makefiles with upstream author attribution | Third-party hold, not relabeled as original code |
| Private session/transcript exporter | Excluded; it collects private workflow records |
| Cached third-party pages, environments, dependency trees and duplicate site snapshots | Not part of the first-party source supplement |
| Newly recovered measurements/coordinates, trained artifacts and label-bearing replay inputs | Not added by this source release; access and redistribution terms remain separate |

The seven uncertain XFOIL helpers are historical diagnostics/no-op compatibility stubs, not a verified functioning XFOIL source distribution. Their exclusion is a provenance boundary, not removal of the original research correction algorithms. Existing public assets keep their histories and applicable terms. This release does not erase earlier Git history.

## Running and interpreting the archive

Use the root-level synthetic suite and named integrity checkers in the [source guide](../code/README.md). Do not recursively run archived tests: some require private arrays, fit models, extract packages or write outputs at import. Historical assertions of “PASS,” review approval or finality describe saved procedures; replaying their recorders is not a fresh human review. Placeholder paths do not make an old script portable.

The website update adds a research explanation and searchable code access while keeping the browser model weights and numerical inference implementation unchanged. **NeuralFoil B** identifies that legacy browser wrapper. The newer Python drag-correction research remains separate; its historical average gains are not universal or pointwise guarantees.

Original code and new accompanying technical documentation fall under the project's MIT scope. This is a source-content and integrity release, not a new accuracy benchmark, safety certification, complete trained-model package or independent experimental replication.
