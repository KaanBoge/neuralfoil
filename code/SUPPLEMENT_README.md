# Additional historical source

`supplement/` contains reviewed first-party Python sources omitted by the earlier directory-based selection. `supplement-manifest.json` records each original and published hash, byte count, known duplicate aliases and literal home-path replacement count. One copy per distinct source version is retained.

This is a **source archive**, not a turnkey manuscript build or complete research runtime. It includes generic layout, packaging, audit and numerical/replay helpers and meaningful failed/obsolete predecessors. Historical assertions and saved-review recorders do not grant approval or establish success for a new run. Referenced private measurements, fitted models, archives, document inputs and frozen receipts are not supplied here. Old source pins remain old pins.

Historical renderers retain their short incidental title/footer/keyword metadata. These are not the paper body, a current publication title decision or approval of a new document build.

Where present, `/Users/kaanboge` was replaced mechanically with `/PATH_TO_YOUR_HOME` in public copies. This is an explicit placeholder, not a portable adapter or verified behavior change. The original private source was not changed.

Check the source bytes without importing research modules:

```sh
python3 -B tools/verify_source_supplement.py
python3 -B -m unittest discover -s tests -p 'test_source_supplement.py'
```

Do not broadly discover tests under `code/` or import historical modules to inspect them: some have import-time file access, some perform expensive research work, and some require deliberately absent private inputs or companion modules. Use the root-level synthetic example/tests for the public quick-start. No measured-accuracy claim follows from source integrity or synthetic tests.
