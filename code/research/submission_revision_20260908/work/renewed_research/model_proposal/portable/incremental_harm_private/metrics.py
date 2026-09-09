import numpy as np
import pandas as pd
import incremental_harm as policy
LABELS=['calibrated_incremental_harm_001', 'proper_capped_half', 'proper_capped_full', 'project_mean8_capped', 'project_xlarge_capped', 'mean8_CD', 'xlarge_CD', 'capped_half', 'capped_full', 'unpenalized_transfer', 'half_strength']
CANDIDATES=['calibrated_incremental_harm_001']
CONTROLS=['proper_capped_half', 'proper_capped_full', 'project_mean8_capped', 'project_xlarge_capped', 'mean8_CD', 'xlarge_CD', 'capped_half', 'capped_full', 'unpenalized_transfer', 'half_strength']
REFERENCES=['unpenalized_transfer', 'half_strength', 'proper_capped_half']
PERFORMANCE='unpenalized_transfer'
ROBUSTNESS='half_strength'
ASSIGNMENTS=[20260906, 20260908]
EXTERNAL=['SG_exposed', 'W_new_challenge']
FIELDS=['xlarge_CD_improvement_percent', 'mean8_CD_improvement_percent']
BASELINES=['xlarge_CD', 'mean8_CD']
ROW_TOL=1e-12
PP_TOL=1e-06
N_BOOTSTRAP=20000
SEED=2026090831

def panel_metrics(frame, panels):
    rows = []
    target = frame.measured_CD.to_numpy()
    for label in LABELS:
        error = abs(frame[label].to_numpy() - target)
        for name, ix in panels.items():
            e = error[ix]
            row = {"candidate": label, "panel": name, "rows": len(ix),
                   "mae_CD": float(e.mean()), "mae_drag_counts": float(e.mean() * 1e4),
                   "median_absolute_error_CD": float(np.median(e)),
                   "p90_absolute_error_CD": float(np.quantile(e, .9)),
                   "row_equality_tolerance_CD": ROW_TOL}
            for baseline in BASELINES:
                be = abs(frame[baseline].to_numpy()[ix] - target[ix])
                assert be.sum() > 0
                row.update({baseline + "_mae": float(be.mean()),
                            baseline + "_improvement_percent": float(100 * (1 - e.sum() / be.sum())),
                            baseline + "_worse_rows": int((e > be + ROW_TOL).sum()),
                            baseline + "_worse_fraction": float((e > be + ROW_TOL).mean())})
            rows.append(row)
    return pd.DataFrame(rows)

def bootstrap(frame):
    rows = []
    for assignment in ASSIGNMENTS:
        f = frame[frame.split.str.startswith(f"group_{assignment}_")]
        assert len(f) == f.nf2_row_id.nunique() == 8371
        groups, inverse = np.unique(f.group, return_inverse=True)
        assert len(groups) == 93
        y = f.measured_CD.to_numpy()
        counts = np.random.default_rng(SEED).multinomial(
            len(groups), np.full(len(groups), 1 / len(groups)), size=N_BOOTSTRAP)
        sums = {label: np.bincount(inverse, weights=abs(f[label].to_numpy() - y)) for label in LABELS}
        resampled = {label: counts @ values for label, values in sums.items()}
        for reference in REFERENCES:
            assert (resampled[reference] > 0).all()
            for label in LABELS:
                benefit = 100 * (1 - resampled[label] / resampled[reference])
                lo, hi = np.quantile(benefit, [.025, .975])
                rows.append({"candidate": label, "assignment": assignment, "reference": reference,
                             "rows": len(f), "groups": len(groups),
                             "remaining_MAE_reduction_percent": float(100 * (1 - sums[label].sum() / sums[reference].sum())),
                             "conditional_95pct_lower": float(lo), "conditional_95pct_upper": float(hi),
                             "bootstrap_fraction_benefit_positive": float((benefit > 0).mean()),
                             "draws": N_BOOTSTRAP, "seed": SEED,
                             "interpretation": "Fixed-prediction paired group bootstrap; adaptive/unadjusted, not confirmatory; assignments overlap"})
    return pd.DataFrame(rows)

def group_metrics(frame):
    rows = []
    for assignment in ASSIGNMENTS:
        f = frame[frame.split.str.startswith(f"group_{assignment}_")]
        assert f.group.nunique() == 93
        for group, part in f.groupby("group", sort=True):
            y = part.measured_CD.to_numpy()
            baseline = abs(part.xlarge_CD.to_numpy() - y).mean()
            assert baseline > 0
            for label in LABELS:
                error = abs(part[label].to_numpy() - y).mean()
                reduction = 100 * (1 - error / baseline)
                rows.append({"candidate": label, "assignment": assignment, "group": group,
                             "rows": len(part), "mae_CD": float(error), "xlarge_mae_CD": float(baseline),
                             "MAE_difference_vs_xlarge_CD": float(error - baseline),
                             "xlarge_improvement_percent": float(reduction),
                             "worse_than_xlarge": bool(reduction < -PP_TOL)})
    return pd.DataFrame(rows)

def harms(frame, panels):
    rows = []
    y = frame.measured_CD.to_numpy()
    for label in LABELS:
        error = abs(frame[label].to_numpy() - y)
        for reference in REFERENCES + BASELINES:
            difference = error - abs(frame[reference].to_numpy() - y)
            for name, ix in panels.items():
                delta = difference[ix]
                positive = np.maximum(delta, 0)
                worse, better = delta > ROW_TOL, delta < -ROW_TOL
                equal = ~(worse | better)
                rows.append({"candidate": label, "reference": reference, "panel": name, "rows": len(ix),
                             "mean_positive_excess_absolute_error_CD": float(positive.mean()),
                             "mean_positive_excess_absolute_error_drag_counts": float(positive.mean() * 1e4),
                             "mean_signed_excess_absolute_error_CD": float(delta.mean()),
                             "p90_positive_excess_absolute_error_CD": float(np.quantile(positive, .9)),
                             "worse_rows": int(worse.sum()), "better_rows": int(better.sum()),
                             "equal_rows": int(equal.sum()), "worse_fraction": float(worse.mean()),
                             "better_fraction": float(better.mean()), "equal_fraction": float(equal.mean()),
                             "row_equality_tolerance_CD": ROW_TOL})
    return pd.DataFrame(rows)

def identity_guard(groups, label, reference):
    rows, passes = {}, True
    for assignment in ASSIGNMENTS:
        c = groups[(groups.candidate == label) & (groups.assignment == assignment)]
        r = groups[(groups.candidate == reference) & (groups.assignment == assignment)]
        assert len(c) == len(r) == 93 and set(c.group) == set(r.group)
        cn = int((c.xlarge_improvement_percent < -PP_TOL).sum())
        rn = int((r.xlarge_improvement_percent < -PP_TOL).sum())
        cw = max(0., float(-c.xlarge_improvement_percent.min()))
        rw = max(0., float(-r.xlarge_improvement_percent.min()))
        ok = cn <= rn and cw <= rw + PP_TOL
        passes &= ok
        rows.update({f"{assignment}_negative_groups": cn, f"{assignment}_reference_negative_groups": rn,
                     f"{assignment}_worst_group_deterioration_percent": cw,
                     f"{assignment}_reference_worst_group_deterioration_percent": rw,
                     f"{assignment}_identity_guard_pass": ok,
                     f"{assignment}_worst_positive_group_MAE_difference_CD": max(0., float(c.MAE_difference_vs_xlarge_CD.max())),
                     f"{assignment}_reference_worst_positive_group_MAE_difference_CD": max(0., float(r.MAE_difference_vs_xlarge_CD.max()))})
    return bool(passes), rows

def decisions(table, boot, groups):
    rows = []
    ext = table.panel.str.startswith("eligible_only/")
    ref = table[(table.candidate == PERFORMANCE) & ext][FIELDS].to_numpy()
    assert ref.shape == (8, 2)
    ref_negative, ref_min = int((ref < -PP_TOL).sum()), float(ref.min())
    for label in CANDIDATES:
        t = table[table.candidate == label]
        assert len(t) == 31
        strict = t[t.panel.str.startswith("strict_source_")][FIELDS].to_numpy()
        e = t[t.panel.str.startswith("eligible_only/")][FIELDS].to_numpy()
        assert strict.shape == (5, 2) and e.shape == (8, 2)
        strict_pass = bool((strict >= -PP_TOL).all())
        count, worst = int((e < -PP_TOL).sum()), float(e.min())
        external_pass = count <= ref_negative and worst >= ref_min - PP_TOL
        row = {"candidate": label, "strict_source_guard_pass": strict_pass,
               "eligible_external_negative_panel_baseline_pairs": count,
               "performance_reference_negative_pairs": ref_negative,
               "minimum_eligible_external_improvement_percent": worst,
               "performance_reference_minimum_eligible_improvement_percent": ref_min,
               "performance_external_guard_pass": external_pass,
               "minimum_all31_improvement_both_percent": float(t[FIELDS].to_numpy().min()),
               "all31_nonnegative_both_baselines": bool((t[FIELDS].to_numpy() >= -PP_TOL).all())}
        for reference, prefix in [(PERFORMANCE, "performance"), (ROBUSTNESS, "robustness")]:
            b = boot[(boot.candidate == label) & (boot.reference == reference)]
            assert len(b) == 2
            gain = bool((b.remaining_MAE_reduction_percent >= 1 - PP_TOL).all())
            group_pass, diagnostics = identity_guard(groups, label, reference)
            row[prefix + "_historical_gain_both_at_least_1pct"] = gain
            row[prefix + "_identity_guard_both_assignments"] = group_pass
            row.update({prefix + "_" + key: value for key, value in diagnostics.items()})
            row[prefix + "_advance"] = bool(gain and group_pass and (
                strict_pass and external_pass if reference == PERFORMANCE else row["all31_nonnegative_both_baselines"]))
        rows.append(row)
    return pd.DataFrame(rows)

def summary(table, boot, groups):
    rows = []
    for label in LABELS:
        t = table[table.candidate == label].set_index("panel")
        row = {"candidate": label, "role": "new_fixed_procedure" if label in CANDIDATES else "fixed_control",
               "minimum_all31_improvement_both_percent": float(t[FIELDS].to_numpy().min()),
               "minimum_eligible8_improvement_both_percent": float(t.loc[t.index.str.startswith("eligible_only/"), FIELDS].to_numpy().min()),
               "worst_strict_source_improvement_both_percent": float(t.loc[t.index.str.startswith("strict_source_"), FIELDS].to_numpy().min())}
        for assignment in ASSIGNMENTS:
            for field in FIELDS + ["mae_CD", "median_absolute_error_CD", "p90_absolute_error_CD"]:
                row[f"{assignment}_{field}"] = float(t.loc[f"history_{assignment}_pooled", field])
            g = groups[(groups.candidate == label) & (groups.assignment == assignment)]
            row[f"{assignment}_negative_identity_groups"] = int((g.xlarge_improvement_percent < -PP_TOL).sum())
            row[f"{assignment}_worst_group_improvement_percent"] = float(g.xlarge_improvement_percent.min())
            for reference in REFERENCES:
                b = boot[(boot.candidate == label) & (boot.assignment == assignment) & (boot.reference == reference)].iloc[0]
                row[f"{assignment}_remaining_MAE_reduction_vs_{reference}_percent"] = float(b.remaining_MAE_reduction_percent)
        rows.append(row)
    return pd.DataFrame(rows)

def make_panels(frame):
    panels = {}
    for seed in [20260906, 20260908]:
        mask = frame.split.str.startswith(f"group_{seed}_").to_numpy()
        panels[f"history_{seed}_pooled"] = np.flatnonzero(mask)
        assert mask.sum() == 8371 and frame.loc[mask, "nf2_row_id"].nunique() == 8371
        for source in sorted(frame.loc[mask, "source"].unique()):
            panels[f"history_{seed}_{source}"] = np.flatnonzero(mask & frame.source.eq(source).to_numpy())
    for split in sorted(s for s in frame.split.unique() if s.startswith("strict_source_")):
        panels[split] = np.flatnonzero(frame.split.eq(split).to_numpy())
    for split in EXTERNAL:
        mask = frame.split.eq(split).to_numpy()
        panels[f"{split}_pooled"] = np.flatnonzero(mask)
        for config in sorted(frame.loc[mask, "configuration"].unique()):
            panels[f"{split}_{config}"] = np.flatnonzero(mask & frame.configuration.eq(config).to_numpy())
        eligible = mask & frame.interval_applicable.to_numpy(bool)
        panels[f"eligible_only/{split}/pooled"] = np.flatnonzero(eligible)
        for config in sorted(frame.loc[mask, "configuration"].unique()):
            panels[f"eligible_only/{split}/{config}"] = np.flatnonzero(eligible & frame.configuration.eq(config).to_numpy())
    assert len(panels) == 31
    return panels

def extra_metrics(frame,panels):
    risk_rows=[];bundle_rows=[];intervention_rows=[]
    for panel,ix in panels.items():
        f=frame.iloc[ix].copy()
        ext=f.split.isin(['SG_exposed','W_new_challenge'])
        assert ext.all() or not ext.any()
        # External nominal design, retaining all configurations in pooled views.
        f['audit_identity']=f.airfoil.astype(str) if ext.all() else f.group.astype(str)
        y=f.measured_CD.to_numpy();b=f.mean8_CD.to_numpy();anchor=f.proper_capped_half.to_numpy()
        for label in LABELS:
            error=abs(f[label].to_numpy()-y)
            delta=error-abs(anchor-y);loss=np.maximum(delta,0)/b
            gm=[]
            for identity,part in f.groupby('audit_identity',sort=True):
                mask=f.audit_identity.eq(identity).to_numpy()
                value=float(loss[mask].mean());gm.append(value)
                bundle_rows.append({'candidate':label,'panel':panel,'identity':identity,
                    'rows':int(mask.sum()),'mean_normalized_positive_excess_vs_matched_half':value})
            risk_rows.append({'candidate':label,'panel':panel,'rows':len(f),'identity_count':len(gm),
                'equal_identity_mean_normalized_positive_excess_vs_matched_half':float(np.mean(gm)),
                'pooled_row_mean_normalized_positive_excess_vs_matched_half':float(loss.mean()),
                'empirical_equal_identity_budget_exceeded':bool(np.mean(gm)>.01),
                'interpretation':'Descriptive reused outcomes, not verification of future IID risk control'})
        pred=f[policy.LABEL].to_numpy();mask=abs(pred-anchor)>1e-12
        row={'panel':panel,'rows':len(f),'eligible_rows':int(f.interval_applicable.sum()),
             'interventions_vs_matched_half':int(mask.sum()),'intervention_fraction':float(mask.mean()),
             'interventions_vs_mean8':int((abs(pred-b)>1e-12).sum()),
             'applied_strength_min':float(f[policy.LABEL+'__strength'].min()),
             'applied_strength_mean':float(f[policy.LABEL+'__strength'].mean()),
             'applied_strength_max':float(f[policy.LABEL+'__strength'].max())}
        for ref in ['proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=abs(pred-y)-abs(f[ref].to_numpy()-y)
            row[ref+'__selected_harm_fraction']=float((d[mask]>1e-12).mean()) if mask.any() else None
            row[ref+'__selected_benefit_fraction']=float((d[mask]<-1e-12).mean()) if mask.any() else None
            row[ref+'__selected_positive_excess_CD']=float(np.maximum(d[mask],0).mean()) if mask.any() else None
        intervention_rows.append(row)
    return pd.DataFrame(risk_rows),pd.DataFrame(bundle_rows),pd.DataFrame(intervention_rows)
