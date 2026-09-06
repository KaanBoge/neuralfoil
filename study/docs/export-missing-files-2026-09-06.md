# Missing files report

Prepared 2026-09-06 at export time and corrected after an independent read-only audit of this document against the files. Nothing listed here was regenerated or re-extracted. Originals are preserved as they exist now; this report says exactly what is absent and where the authoritative original of each absent item lives.

## 1. Extracted low-speed corpus files were deleted after the runs completed

All six directories that held the unzipped UIUC archives under `scratchpad/lsat/` were modified between 2026-08-30 00:30 and 01:30, more than four hours after the last run that read them finished (2026-08-29 20:37). Most extracted members are gone. Windows Storage Sense is enabled on this machine with its temporary-file cleanup flag on (registry record in `records/env/storage-sense-registry.txt`), and the working folder lives inside `AppData\Local\Temp`. The deletion is consistent with a Storage Sense temp cleanup. The exact selection rule was not determined: survivors carry 1989 and 1998 archive timestamps just like the deleted members, so age alone does not explain the pattern.

| Original archive (present, intact) | Members in archive | Still on disk | Missing |
|---|---|---|---|
| `scratchpad/lsat/volume01.zip` | 11 | 4 (FORMAT01.TXT, GPL.TXT, LIFT01.TXT, README01.TXT) | 7, including DRAG01.TXT and COORD01.TXT |
| `scratchpad/lsat/volume02.zip` | 11 | 0 | 11, including DRAG02.TXT and LIFT02.TXT |
| `scratchpad/lsat/volume03.zip` | 10 | 0 | 10, including DRAG03.TXT and LIFT03.TXT |
| `scratchpad/lsat/volume06.zip` | 142 | 0 | 142: the Williamson flapped-airfoil thesis data, six model families (AG40d 22 files, AG455ct 24, W1011-20 24, W1011-30 24, W1015-20 24, W1015-30 24), never used |
| `scratchpad/lsat/Stec8.zip` | 193 | 4 (ALL.DAP, ALL.PD, AQUILA.06, DF103.COR) | 189, including 52 of the 53 .COR geometries (the surviving DF103.COR is a 125-byte placeholder stating that no coordinates exist for that airfoil) |
| `scratchpad/lsat/coord_seligFmt.zip` | 1,665 | 0 | 1,665 .dat coordinate files |

What this means for the science: nothing that was computed is affected. Every derived product was written while the extracted files were present and is intact in this export, with SHA-256 checksums: `lsat-corpus.csv` (all 14,773 parsed measurements), `lsat-geometry.json` (geometry matches), `lsat-geofeat.json`, `lsat-nf.csv` and `lsat-nf2.csv` (all eight model sizes at every geometry-matched measured condition, 13,394 of the 14,773 rows), `lsat-xfoil.csv`, `nfb-measured.json`, the correction models, and every report. The six zip archives are the unmodified downloads from m-selig.ae.illinois.edu and are the authoritative originals; unzipping each into its folder reproduces byte-for-byte what the scripts read. That restoration was deliberately not performed here. The one consequence: the double-clean re-analysis started at export time (`lsat_doubleclean.py`, see `MANIFEST.md` section "Known issues") reads geometry directly from the archive streams in memory instead of from extracted files.

## 2. Items that never existed (correct absences, not losses)

- `correction-cd2.json`: never written. The drag correction v2 failed the declared ship rule (one cross-facility transfer worsened), and `lsat_correction2.py` writes the file only on a pass.
- `correction-cl3-unused.json`: never written by design (`lsat_correction3.py` disabled the lift branch).
- `volume06/volume06/DRAG06.TXT`: never existed; volume 6 ships per-configuration `.dat` files under `vol6/` instead. `lsat_parse.py` reported it as MISSING at run time and skipped the volume.
- LSAT volumes 4 and 5 measured data: never downloaded. Only PDF-tabulated versions exist online; no ASCII data was available (fetch attempts for `vol4/DRAG04.TXT` and the vol5 equivalents returned not found).
- `lsat_geom.py` unmatched-entry list: printed to the console at run time and not saved to a file. It is reconstructed in `UNUSED-DATA.md` from `lsat-corpus.csv` and `lsat-geometry.json`, which are the exact inputs it was derived from.
- First atlas attempt log: the process was started with nohup and died with its WSL session; no log survives. The completed rerun is the atlas in `scratchpad/data/atlas-out/`.
- First corpus XFOIL attempt output: crashed at worker-pool creation (Python 3.14 forkserver under WSL) before writing a CSV; the failure log is `logs/tasks/b3mrqjuw9.output`. The completed thread-pool rerun is `lsat-xfoil.csv`.
- The first run of the release-verification workflow was killed by a PC shutdown; its journal is preserved and the resumed run completed (`logs/workflows/wf_79aecf48-407/`).

## 3. Broken or partial items included as found

- `scratchpad/ghpages/.git` has no HEAD file and is not a valid repository; the working files in `scratchpad/ghpages/` are intact.
- `scratchpad/data/:00.bl` and `scratchpad/lsat/:00.bl`: 6,635-byte artifacts of a mangled shell command; kept as found.

## 4. Apparent missing references that are not real

A scan of every script for quoted filenames flagged three names that do exist: `a.dat` and `p.txt` are XFOIL temporary files created inside per-run temp directories, and `manifest.json` is `scratchpad/data/nfweights/manifest.json`.

## 5. Things outside the working folder that were part of the runs

- `~/nfenv` in WSL (720 MB virtual environment): not copied; recorded exactly by `records/env/pip-freeze-nfenv.txt` and `python-version.txt`.
- XFOIL in WSL: the built binary `~/Xfoil/bin/xfoil`, the six headless stub sources from `~/Xfoil/stublib/`, and the three Makefiles from `~/Xfoil/bin/` are copied to `records/env/xfoil/`, together with the original 6.99 source tarball, which lived at `~/xfoil.tgz` in the WSL home directory (the tarball itself contains the full source tree with its other Makefiles). The rest of the extracted `~/Xfoil` tree and its `runs/` scratch are not copied separately.
- `~/parity.py` in WSL: copied to `records/env/xfoil/home-parity.py`; it differs from `site-repo/neuralfoil/study/tools/parity.py`.
- Claude memory files and the cloud-crushing project files in the same WSL home are unrelated to this work and were not included.

## 6. Risk notice

The C: drive had about 2.2 GB free at export time, and the working folder remains inside the Windows Temp tree where the deletion above happened. Moving this archive out of `AppData\Local\Temp` is the single most important preservation step.
