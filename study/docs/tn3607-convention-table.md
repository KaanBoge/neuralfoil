# NACA TN 3607: Convention Table and Sanity-Gate Result

Required by frozen Methods Step 3 before any bulk extraction from this source. Completed 2026-08-25 by reading the report text with page citations and by running the gate on the pinned Python path. TN 3607 is the study's PRIMARY CALIBRATION source, so these conventions govern the largest single block of data the paper will use.

## 1. Convention table

| Item | Finding | Where read |
|---|---|---|
| **Tunnel** | Langley 4- by 19-inch semiopen tunnel, an INDUCTION tunnel drawing atmospheric air. Open-throat type: the side walls are fixed but the flow over the top and bottom of the test section is unrestrained, with an external duct connecting the upper and lower chambers. The report states this arrangement is not subject to the usual choking limitations of a closed-throat tunnel. | scan p.6, p.8, p.10 |
| **Model size** | 4-inch chord; models completely span the 4-inch dimension of the tunnel. Static-pressure orifices of 0.0135-inch diameter drilled normal to the surface near midspan. | scan p.13 |
| **Lift convention** | **NORMAL-FORCE COEFFICIENT c_n ONLY.** There is no measured lift coefficient anywhere in the report. The only c_l symbol is c_l_i, the design (incompressible) lift coefficient used to LABEL the camber series (the 2 and 5 in 64A206 and 64A506); it is a geometry parameter, not a measurement. Figure 10's left panel is labeled "Section normal-force coefficient, c_n". | symbols list scan p.7; text scan p.14; axis labels scan p.37 |
| **Axis-system warning** | c_n comes from chordwise pressure integration, so it is normal to the CHORD. c_d comes from a wake total-pressure survey, so it is in the STREAM direction. **They are not in the same axis system**, and chord force is never measured. The report's own efficiency parameter is n/d, the section normal-force-drag ratio, not L/D. | scan p.13, p.17 |
| **Reynolds number** | **Varies strongly with Mach: 0.7 x 10^6 at M 0.30 rising to 1.6 x 10^6 at M 1.00.** Stated as endpoints in three places. There is NO Reynolds-versus-Mach chart or table anywhere in the report (every apparatus and calibration figure was checked). | scan p.5, p.13, p.22 |
| **Transition** | **NOT STATED.** The words transition, trip, roughness, and surface finish do not appear anywhere in the report. Free transition is an inference from silence, not a statement. Complication: the 0.0135-inch pressure orifices are drilled through the surface at forward-chord stations and are a potential distributed trip that the report never discusses. | scan pp.5-24 (all text pages) |
| **Angle convention** | Plotted angles are alpha_test, the UNCORRECTED angle of attack. The normal-force-curve slope symbol is likewise defined as uncorrected, dc_n/dalpha_test. | symbols list scan p.7; text scan p.14 |
| **Geometry** | EXACT. Table I on scan p.25 gives published ordinates for all nine sections. Transcribed to tn3607-ordinates.csv and tn3607-ordinates-cambered.csv. This is the only source in the study whose geometry needs no digitization. | scan p.25 |

### Derived Reynolds-versus-Mach curve (flagged as derived, not read)

The report gives only endpoints, but the tunnel physics fixes the shape: an induction tunnel draws atmospheric air, so stagnation conditions are fixed and Re follows the isentropic expansion. Assuming sea-level stagnation, Sutherland viscosity and the stated 4-inch chord reproduces BOTH published endpoints to within 3 percent (0.68 x 10^6 against the stated 0.7, and 1.58 x 10^6 against the stated 1.6), which is strong evidence the assumption is right.

| M | 0.30 | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 | 1.00 |
|---|---|---|---|---|---|---|---|---|
| Re (millions) | 0.68 | 0.88 | 1.06 | 1.22 | 1.35 | 1.45 | 1.53 | 1.58 |

**This shape matters.** Reynolds nearly doubles between M 0.30 and M 0.70 and then flattens. Every Reynolds-sensitive prediction must be re-run per Mach point over the low-Mach half of a sweep; above M 0.8 a single Re of about 1.5 x 10^6 suffices.

## 2. Sanity-gate result (Methods Step 3, threshold 10 drag counts)

Measured cd at alpha_test = 0 for the four thickness-series sections, read from the Figure 10 drag panels, against NeuralFoil evaluated at each point's own Reynolds number.

| Section | Measured cd at M 0.30 | NeuralFoil (n_crit 6) | Gap | Mean gap over M 0.30 to 0.60 |
|---|---|---|---|---|
| 64A004 | 0.0050 | 0.00410 | +9.0 counts | +10.0 |
| 64A006 | 0.0053 | 0.00439 | +9.1 counts | **+7.7 (PASSES at all four Mach numbers)** |
| 64A009 | 0.0067 | 0.00557 | +11.3 counts | +9.7 |
| 64A012 | 0.0046 | 0.00627 | **-16.7 counts (wrong sign)** | -11.7 |

**Verdict: the strict absolute gate fails on three of four sections, and 64A006 passes cleanly at n_crit 6 on all four Mach numbers.** As with Ferri, this source therefore enters the study in increment-only mode under amendment A8, which is not a problem for the design: Step 8's fitting target is the drag-rise increment, which subtracts exactly this kind of per-facility offset.

### Two findings that make the failure informative rather than fatal

**(a) The offset is consistent across three sections.** At n_crit 6 the measured-minus-predicted offsets are +9.5, +7.5 and +9.5 counts for the 4, 6 and 9 percent sections. A common offset of about +8 counts across three different models is the signature of a facility effect (low Reynolds number, surface orifices, blockage) rather than random error.

**(b) NeuralFoil reproduces the Reynolds-driven trend it should.** Because Re rises with Mach in this tunnel, subcritical drag FALLS with Mach, which is a physics effect the model must capture independently of any offset. Measured declines from M 0.30 to 0.60 are 6.0, 7.0 and 11.0 counts for the three well-behaved sections; NeuralFoil predicts 7.0, 3.8 and 7.3. The trend is right to within a few counts while the level is offset. That is precisely the evidence that justifies fitting increments.

### The 64A012 anomaly, reported rather than smoothed

The measured zero-lift drag is NOT monotonic in thickness: 0.0050, 0.0053, 0.0067, 0.0046 for the 4, 6, 9 and 12 percent sections. The 12 percent section reads lower than both the 9 and the 6. NeuralFoil, by contrast, orders them monotonically (0.00418, 0.00431, 0.00529, 0.00621), as physics requires.

This was checked three ways before being accepted: the page-to-airfoil captions were read directly (scan p.38 is the NACA 64A009 small-duct page, scan p.39 the NACA 64A012 small-duct page), the drag panels of both pages were re-rendered and compared independently, and the axis calibration was re-derived by two separate routes agreeing to better than 1 percent. **The anomaly is in the published figure, not in the extraction.** The 64A012 is also the only section whose drag rises rather than falls between M 0.50 and 0.60, against the Reynolds trend every other section follows.

Disposition: flag the 64A012 zero-lift level as anomalous, do not use it as a gate anchor, and check it against its own duct-comparison counterpart before it enters the fit. The likeliest physical explanations are a model-to-model difference in surface finish or transition location, which the report does not document, or a blockage difference at 12 percent thickness in a 19-inch test section.

## 3. Consequences for the frozen protocol (proposed amendments)

**A13. The subcritical baseline for TN 3607 cannot be a constant.** Amendment A1 defines the baseline as the mean CD over a plateau window. That is correct for Ferri, whose tunnel held Reynolds constant, but WRONG here: this tunnel's Reynolds rises with Mach, so the true subcritical baseline declines by 6 to 11 counts across M 0.30 to 0.60. Using a flat mean would inject a false 6 to 11 count increment before any wave drag exists. For TN 3607 the baseline must be the Reynolds-corrected subcritical prediction shape anchored to the measured level, or equivalently a fitted smooth function of Mach over the subcritical range. This must be settled before extraction, because it changes every increment the source contributes.

**A14. n_crit for the Langley 4 by 19 inch semiopen tunnel.** The gate is best satisfied at n_crit 6, not 9 (64A006 passes at all four Mach numbers at n_crit 6 and fails three of four at n_crit 9). Record n_crit 6 as this facility's convention entry, noting it is an inference because the report never states its transition condition, and noting the pressure orifices as an unquantified trip risk. This is the second facility whose measured n_crit falls below the originally registered 7-to-11 sweep, supporting amendment A12.

**A15. The c_n to c_l conversion must be declared.** TN 3607 reports normal force, NeuralFoil predicts lift, and the two differ by the chord-force term that this report never measured. For the fixed-lift comparisons Step 5 requires, the defensible options are: convert the PREDICTION to normal force via c_n = c_l cos(alpha) + c_d sin(alpha) using the predicted c_d as the chord-force proxy, or restrict TN 3607 comparisons to low angles where the difference is under 1 percent. The first is preferred and must be written into the Methods before extraction. Note that at alpha_test = 0 on a symmetric section the distinction vanishes, which is why the gate above is unaffected.

## 4. Status

Convention table COMPLETE. Sanity gate RUN and recorded. TN 3607 is cleared for extraction in increment-only mode, subject to amendments A13, A14 and A15 being settled with the mentor first, because A13 in particular changes every number the source will contribute. The 37-curve extraction list is already prepared in tn3607-curve-list.md and awaits the same mentor sign-off.
