# Experimental data never used during model development

Counted at export time from the original archives and the derived files, then corrected after an independent read-only audit re-measured every figure. "Used" means it entered core selection, correction training, validation, or a published comparison. Counts from the archives were read from the zip streams in memory, not from the deleted extracted copies. Two audit findings about data that WAS used but should not have been are in `MANIFEST.md`, section "Known issues".

## 1. UIUC low-speed corpus (Summary of Low-Speed Airfoil Data vols 1 to 3, SoarTech 8, Williamson vol 6)

### Lift measurements

| Source | Points in original | Used | Never used |
|---|---|---|---|
| Volume 1 LIFT01.TXT | 10,816 | | |
| Volume 2 LIFT02.TXT | 7,963 | | |
| Volume 3 LIFT03.TXT | 13,655 | | |
| SoarTech 8 per-Reynolds lift files, standard names | 14,651 | | |
| SoarTech 8 per-Reynolds lift files with a suffix letter (9 files: HQ2-9A.06B/.06C/.06D, HQ2-9B.20T, MB253515.08R, S2091B.20G, S4233.10R, SD7084.10R, SD7090.08R) | 914 | 0 | 914, never parsed (the filename pattern skipped them) |
| Total vols 1 to 3 + SoarTech 8 | 47,999 | 31,075 | 16,924 |
| Volume 6 (flapped-airfoil thesis: AG40d, AG455ct, W1011 and W1015 with 20 and 30 percent flaps; 80 lift files, 278 Reynolds blocks) | 12,592 | 0 | 12,592, never parsed |

Of the 16,924 unused points, 914 are the suffixed SoarTech files above; the other 16,010 belong to entries that were either modified configurations (trips, tapes, flaps, coverings, thick trailing edges), could not be matched to public geometry, or to lift files whose entry was not a clean match.

### Drag measurements

| Source | Points in original | Used | Never used |
|---|---|---|---|
| Volume 1 DRAG01.TXT | 1,661 | | |
| Volume 2 DRAG02.TXT | 1,669 | | |
| Volume 3 DRAG03.TXT | 3,681 | | |
| SoarTech 8 ALL.PD | 7,762 | | |
| Total parsed (lsat-corpus.csv) | 14,773 | 10,608 | 4,165 |
| Volume 6 (flapped) drag files (62 files, 184 Reynolds blocks) | 3,094 | 0 | 3,094, never parsed |

The 4,165 unused drag points decompose as 1,326 from the 26 entries with no matching public geometry, 2,786 from the 54 matched entries whose names carry configuration modifiers, and about 53 from the DF103 geometry-parse failure and residual. Of the 10,608 rows used, 10,312 lie inside the declared correction domain; the other 296 (outside Re 600,000, |alpha| 12 degrees, or t/c 5 to 20 percent) were used for validation maps but never for correction training. Note that the 10,608 "used" rows include 1,974 rows that the Comment field marks as modified configurations; see `MANIFEST.md`, "Known issues".

### Entries excluded and why

Unmatched to any public geometry (26; 1,326 drag points): stec8|FLAT PLATE (flat plate, excluded by design); stec8|NACA 2.5411; stec8|S2091B GFA; stec8|S2091B GFB; stec8|S2091B GFC; stec8|S4061B TWO UST AT 150k AND 300k; stec8|SD7032A SANDED BALSA FINISH; stec8|SD7032C PF6; stec8|SD7062 PLAIN and TWO TRIPS; stec8|SD7090 LOOSE, TIGHT COVERING; stec8|SD7090 VARIOUS TRIPS; stec8|WB140/35/FB; vol1|CH 10-48-13; vol1|FX 74-CL5-140 MOD; vol1|M06-13-128 (B); vol1|S822; vol1|S823; vol2|Davis 3R; vol2|LD-79; vol2|M06-13-128 (B); vol2|S822; vol2|S823; vol3|CG Ultimate; vol3|ESA; vol3|Falcon 56 Mk III; vol3|Ultra-Sport 1000.

Matched but excluded as modified configurations (54; 2,786 drag points): stec8|DAE51 THICK T.E.; stec8|E193 MODIFIED; stec8|E214C F0, UST .020, .125, 20%; stec8|E214C NF3; stec8|E214C NF6; stec8|E214C PF3; stec8|E374B BUMP SHOT TRIP 50%; stec8|E374B CLAY L.E.; stec8|E374B THICK T.E.; stec8|E374B UST .020, .125, 20%; stec8|E387A HIGH TURBULENCE; stec8|E387A REPEAT; stec8|E387A UST .020, .125, 20%; stec8|HQ2/9A LST .020, .125, 50%; stec8|HQ2/9A UST .020, .125, 20%; stec8|HQ2/9A UST .020, .125, 40%; stec8|HQ2/9A UST .020, .125, 50%; stec8|HQ2/9B BLOWING TYPE B, 50%; stec8|HQ2/9B TRIPS AT 200k; stec8|MB253515 UST .020, .125, 20%; stec8|MILEY BUMP SHOT TRIP 31%; stec8|MILEY UST AT 200k; stec8|RG15 UST (20%, 40%, 60%, 70%: four entries); stec8|S2048 LST 60% UST 63%; stec8|S2048 TRIPS AT 300k; stec8|S2055 REPEAT; stec8|S4061B UST .020, .125, 45%; stec8|S4061B UST AT 150k; stec8|S4233 UST .020, .125, 20%; stec8|SD6060 UST (20%, 40%: two entries); stec8|SD6080 THICK T.E.; stec8|SD6080 UST (10%, 20%, 30%: three entries); stec8|SD7003 BUMP SHOT TRIP (50%, 60%, 70%: three entries); stec8|SD7003 REPEAT; stec8|SD7003 UST (60%, 70%: two entries); stec8|SD7032C NF3; stec8|SD7032C NF6; stec8|SD7032C PF3; stec8|SD7032D UST .020, .125, 45%; stec8|SD7037 UST .020, .125, 30%; stec8|SD7043 UST .020, .125, 20%; stec8|SD7062 UST .020, .125, 15%; stec8|SD8000 UST (20%, 40%, 70%: three entries).

Note that "REPEAT" and "HIGH TURBULENCE" entries are repeat or altered-tunnel runs of clean airfoils; they were excluded by the name-token rule and represent usable clean-geometry data that a future study could recover.

### Files in the archives never used at all

- COORD01.TXT, COORD02.TXT, COORD03.TXT: the measured coordinates of the tested models. Not used because the volume README states they are not under the public license; nominal public-database geometry was used instead.
- ALL.DAP (SoarTech 8 digitized-coordinate file): not used.
- Pitching-moment columns: LIFT01.TXT and LIFT02.TXT carry a header stating their moment data is meaningless, and were rightly ignored. LIFT03.TXT carries no such header; its 13,655 rows hold real measured Cm values (2,535 distinct values; the volume 3 README states moment data is available for that volume), and the 80 volume 6 lift files hold another 12,592 Cm rows. About 26,000 measured pitching-moment points therefore exist in the archives and were never used. The SoarTech per-Reynolds lift files have no Cm column.
- README, BOOK, ACK, MANIFEST, OLD2NEW, FORMAT and DATA0x.PDF documentation files: read for format, no data taken.
- Of the 53 SoarTech .COR profiler geometries, 49 were used as the geometry of matched entries (48 of them for entries in the validation set). Four were referenced by no entry: E193MOD.COR, NACA2411.COR, NACA64.COR, WB14035.COR.

## 2. XFOIL head-to-head

XFOIL was submitted only the conditions clean by both name and comment: 8,706 rows, 8,705 distinct conditions, of which 53 belong to stec8|DF103, whose placeholder .COR holds no coordinates and could not load. It converged on 7,897 (90.7 percent of submitted; 91.3 percent of loadable). The 755 loadable conditions that diverged have no XFOIL result; the divergence rate is a finding. The published figure of 74.7 percent convergence is wrong; see `MANIFEST.md`, "Known issues".

## 3. Transonic phase source reports (scratchpad/data/*.pdf)

| Report | Status |
|---|---|
| tr824.pdf (NACA TR-824, Abbott and von Doenhoff, about 100 airfoils at Re 3 to 9 million) | Downloaded, never extracted. Scanned figures only. |
| tp2890.pdf (NASA TP-2890, supercritical boundary probe) | Downloaded, never extracted. |
| tn1813.pdf (NACA TN 1813, cross-facility check) | Downloaded, never extracted. |
| tm1240.pdf (NACA TM 1240, Gothert) | Downloaded, never extracted. |
| mccroskey.pdf (NASA TM-100019) | Used only to rank data-source quality tiers; no measurements extracted. |
| tn1546.pdf (NACA TN 1546) | 8 of 24 airfoils extracted (16-009, 16-109, 16-209, 16-306, 16-309, 16-312, 16-315, 16-509) per the pre-declared subset; 16 airfoils never extracted; 7 extracted drag points dropped by the declared u_cd > 0.0015 rule (list printed by assemble_tn1546.py at run time; the underlying reads are in tn1546-journal.jsonl); pitching-moment panels never extracted. |
| tn3607.pdf (NACA TN 3607) | Six sections extracted (64A004, 64A006, 64A009, 64A012, 64A206, 64A506); 64A012 excluded from gates as non-monotonic in the published figure; the 32 extracted points above Mach 0.94 (at M 0.95, 0.975 and 1.0: 64A004 5, 64A006 4, 64A009 6, 64A012 6, 64A206 7, 64A506 4) were never used because fit_definitive.py keeps M at or below 0.90; the figure 17 drag-rise points (tn3607-fig17.csv, 87 points) were used only by assembly checks (assemble_tn3607.py, fig17_check.py), never by a fit; moment panels never extracted. |
| harris-tm81927.pdf (NASA TM-81927) | Figure 8 only (47 points across four series); every other figure never digitized. The 9-million fixed-transition series was demoted to quality tier 2 for its trip overdrag but was still used: it is sweep H8-9F in the one-shot holdout (score_holdout.py, holdout-scores.json: n 5) and its rows at M up to 0.70 entered the core-candidate ranking (eval_ensemble.py, eval_ensemble_tight.py), phaseA.py and recompute.py. |
| ferri-wrl143.pdf (Ferri, Guidonia) | 45 corrected drag points and 60 lift points used. ferri-re.csv (Reynolds-variation reads) and ferri-qc-sample.csv (8 QC reads) are referenced only by build-master.ps1 for dataset assembly and never entered a fit. ferri-2309.csv and master-dataset.csv each hold 2 points at Mach 0.941, the highest Mach actually compared. |

tn3607-gate-anchors.csv and tn3607-convention-table.md are documentation tables referenced by no script.

## 4. Extraction intermediates (not measurements)

h58-lower-runs.csv, h58-upper-runs.csv, top_runs.txt, rise1.txt, rise2.txt, rise3.txt, risetraj.txt, flat38.txt, bundle_runs.txt, gridzone_runs.txt, ferri.txt, harris.txt, PScan.cs, 626 jpg crops and 31 png renders: pixel-trace scratch from the pdf.js digitization pipeline, consumed through PowerShell script parameters, never model inputs. Kept in full.

## 5. Data that was never collected anywhere in the study

- Pitching-moment measurements from the transonic reports: none extracted. (Low-speed moment data does exist unused in the LSAT archives; see section 1.)
- Measured data between Re 600,000 and the transonic reports: none exists publicly.
- Independent second reads of the TN 3607 and TN 1546 extractions (single-read only).
