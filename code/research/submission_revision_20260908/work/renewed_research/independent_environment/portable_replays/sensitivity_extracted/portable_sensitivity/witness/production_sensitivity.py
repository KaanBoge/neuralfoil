"""Frozen-prediction target sensitivity. No fitting, gates or outcomes selected here."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
REPORT_HASH = "7e6a3d074c0aaa6c433cf2f598a1e1866fa8e3c202a99959cbb4b4161fcb0dee"
PROTOCOL_HASH = "b1079f3bf53638000d48c910ab3459c62b98c25e81afd2b8349ebf06e099ee9f"
PROCEDURES = ["unpenalized_transfer", "half_strength", "mean8_CD", "xlarge_CD"]
BASELINES = ["mean8_CD", "xlarge_CD"]
RADII_COUNTS = [0, .25, .5, 1, 2, 5, 10, 20]
ATOL_CD = 1e-13
RADIUS_TOL_CD = 1e-12
LD = np.longdouble


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arrays(b, c, y, w):
    result = tuple(np.asarray(a, dtype=LD) for a in (b, c, y, w))
    if any(a.ndim != 1 or a.shape != result[0].shape for a in result):
        raise ValueError("aligned, nonempty 1-D arrays required")
    if not len(result[0]) or not all(np.isfinite(a).all() for a in result):
        raise ValueError("finite, nonempty arrays required")
    if any((a < 0).any() for a in result) or not result[3].sum() > 0:
        raise ValueError("nonnegative predictions, labels, weights required")
    return result


def margin(b, c, target, r):
    return (LD(1) - LD(r)) * np.abs(b-target) - np.abs(c-target)


class RowBox:
    def __init__(self, b, c, y, w, r):
        self.b, self.c, self.y, self.w = arrays(b, c, y, w)
        if not 0 <= r <= 1:
            raise ValueError("r must be a fractional target in [0,1]")
        self.r = r
        self.zero = r == 0 and np.array_equal(self.b, self.c)
        self.observed = float(np.sum(self.w * margin(self.b, self.c, self.y, r)))

    def bounds(self, epsilon):
        if not np.isfinite(epsilon) or epsilon < 0:
            raise ValueError("finite nonnegative radius required")
        if epsilon == 0:
            return self.observed, self.observed
        if self.zero:
            return 0., 0.
        lo, hi = np.maximum(0, self.y-LD(epsilon)), self.y+LD(epsilon)
        # Clipped prediction knots are inside the interval; duplicate endpoints are harmless.
        values = np.stack([margin(self.b, self.c, t, self.r) for t in
                           (lo, hi, np.clip(self.b, lo, hi), np.clip(self.c, lo, hi))])
        return (float(np.sum(self.w * values.min(axis=0))),
                float(np.sum(self.w * values.max(axis=0))))

    def minimum_baseline_mae(self, epsilon):
        lo, hi = np.maximum(0, self.y-LD(epsilon)), self.y+LD(epsilon)
        return float(np.sum(self.w * np.maximum(np.maximum(lo-self.b, self.b-hi), 0)))


class ShiftCurve:
    """One shared shift block; preserve its original mass, not normalized block mass."""
    def __init__(self, b, c, y, w, r):
        self.b, self.c, self.y, self.w = arrays(b, c, y, w)
        if not 0 <= r <= 1:
            raise ValueError("r must be in [0,1]")
        self.r = r
        self.zero = r == 0 and np.array_equal(self.b, self.c)
        knots = np.concatenate([-self.y, self.b-self.y, self.c-self.y])
        changes = np.concatenate([LD(r)*self.w, 2*(1-LD(r))*self.w, -2*self.w])
        order = np.argsort(knots, kind="stable")
        sorted_knots, sorted_changes = knots[order], changes[order]
        starts = np.r_[0, np.flatnonzero(np.diff(sorted_knots) != 0)+1]
        self.knots = sorted_knots[starts]
        changes = np.add.reduceat(sorted_changes, starts)
        self.slopes = np.cumsum(changes)
        left = np.sum(self.w * ((1-LD(r))*self.b-self.c))
        self.values = left + np.r_[LD(0), np.cumsum(self.slopes[:-1]*np.diff(self.knots))]

    def direct(self, delta):
        if self.zero:
            return LD(0)
        return np.sum(self.w * margin(self.b, self.c, np.maximum(0, self.y+LD(delta)), self.r))

    def evaluate(self, delta):
        ix = np.searchsorted(self.knots, delta, side="right")-1
        if ix < 0:
            return self.values[0]
        return self.values[ix] + self.slopes[ix]*(LD(delta)-self.knots[ix])

    def bounds(self, epsilon):
        if self.zero:
            return LD(0), LD(0)
        if epsilon == 0:
            v = self.direct(0)
            return v, v
        low = np.searchsorted(self.knots, -LD(epsilon), side="left")
        high = np.searchsorted(self.knots, LD(epsilon), side="right")
        locations = np.r_[-LD(epsilon), self.knots[low:high], LD(epsilon)]
        values = np.r_[self.evaluate(-LD(epsilon)), self.values[low:high], self.evaluate(LD(epsilon))]
        # Re-evaluate extremizers directly, so slope-integration roundoff does not
        # itself create near-root sign crossings. Long double is a stability aid,
        # not an assertion of exact arithmetic or cross-platform bitwise identity.
        return self.direct(locations[np.argmin(values)]), self.direct(locations[np.argmax(values)])


class SharedShifts:
    def __init__(self, b, c, y, w, r, blocks):
        b, c, y, w = arrays(b, c, y, w)
        blocks = np.asarray(blocks)
        if blocks.shape != b.shape:
            raise ValueError("one block label per row required")
        self.curves = [ShiftCurve(b[blocks == k], c[blocks == k], y[blocks == k],
                                  w[blocks == k], r) for k in np.unique(blocks)]
        self.observed = float(np.sum(w*margin(b, c, y, r)))

    def bounds(self, epsilon):
        if not np.isfinite(epsilon) or epsilon < 0:
            raise ValueError("finite nonnegative radius required")
        if epsilon == 0:
            return self.observed, self.observed
        bounds = np.asarray([c.bounds(epsilon) for c in self.curves], dtype=LD)
        return tuple(float(x) for x in bounds.sum(axis=0))


def first_zero(model, r, limit=1., tolerance=RADIUS_TOL_CD):
    observed = model.bounds(0)[0]
    record = dict(observed_margin_CD=observed, radius_status=None,
                  radius_lower_CD=None, radius_upper_CD=None,
                  lower_endpoint_margin_CD=None, upper_endpoint_margin_CD=None,
                  lipschitz_radius_CD=observed/(2-r) if observed > 0 else None,
                  search_limit_CD=limit, absolute_bracket_tolerance_CD=tolerance)
    if observed <= 0:
        record.update(radius_status="observed_negative" if observed < 0 else "observed_zero",
                      radius_lower_CD=0., radius_upper_CD=0.,
                      lower_endpoint_margin_CD=observed, upper_endpoint_margin_CD=observed)
        return record
    lower, upper = 0., min(1e-4, limit)
    while model.bounds(upper)[0] > 0 and upper < limit:
        lower, upper = upper, min(upper*2, limit)
    upper_margin = model.bounds(upper)[0]
    if upper_margin > 0:
        record.update(radius_status="right_censored", radius_lower_CD=limit,
                      lower_endpoint_margin_CD=upper_margin)
        return record
    while upper-lower > tolerance:
        mid = (lower+upper)/2
        if model.bounds(mid)[0] > 0:
            lower = mid
        else:
            upper = mid
    record.update(radius_status="finite_bracket", radius_lower_CD=lower, radius_upper_CD=upper,
                  lower_endpoint_margin_CD=model.bounds(lower)[0],
                  upper_endpoint_margin_CD=model.bounds(upper)[0])
    assert record["lower_endpoint_margin_CD"] > 0
    assert record["upper_endpoint_margin_CD"] <= 0
    assert upper-lower <= tolerance
    assert upper+ATOL_CD >= record["lipschitz_radius_CD"]
    return record


def load():
    assessment = PROJECT/"model_development_20260908_adaptive_scale/assessment"
    report_path = assessment/"report.json"
    assert sha(report_path) == REPORT_HASH
    report = json.loads(report_path.read_text())
    assert sha(HERE/"PROTOCOL.md") == PROTOCOL_HASH
    hashes = {str(report_path): REPORT_HASH, str(HERE/"PROTOCOL.md"): PROTOCOL_HASH,
              str(Path(__file__).resolve()): sha(__file__)}
    rows, metrics = assessment/"all_row_predictions.csv", assessment/"panel_metrics.csv"
    helper = PROJECT/"model_development_20260907_selective/assess_selective.py"
    for path, field in [(rows, "output_sha256"), (metrics, "output_sha256"), (helper, "input_source_sha256")]:
        hashes[str(path)] = report[field][str(path)]
        assert sha(path) == hashes[str(path)], path
    frame = pd.read_csv(rows, low_memory=False)
    old = pd.read_csv(metrics)
    spec = importlib.util.spec_from_file_location("frozen_panel_membership", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frame["interval_applicable"] = module.boolean(frame.interval_applicable)
    panels = module.make_panels(frame)
    assert len(frame) == 29856 and set(panels) == set(old.panel)
    previous = None
    for seed in [20260906, 20260908]:
        f = frame.iloc[panels[f"history_{seed}_pooled"]].sort_values("nf2_row_id")
        assert f.group.nunique() == 93
        if previous is not None:
            for key in ["nf2_row_id", "group", "measured_CD"] + BASELINES:
                np.testing.assert_array_equal(f[key].to_numpy(), previous[key].to_numpy())
        previous = f
    assert (frame[PROCEDURES+BASELINES].to_numpy() > 0).all()
    assert (frame.measured_CD.to_numpy() >= 0).all()
    assert np.isfinite(frame[PROCEDURES+["measured_CD"]].to_numpy()).all()
    return frame, panels, old, hashes


def run(output):
    started = time.monotonic()
    if output.exists():
        raise FileExistsError("Use a new attempt directory; no overwriting evidence")
    output.mkdir(parents=True)
    tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", "test_sensitivity"],
                           cwd=HERE, text=True, capture_output=True)
    (output/"synthetic_tests.txt").write_text(tests.stdout+tests.stderr)
    if tests.returncode:
        raise RuntimeError("Synthetic tests failed before empirical input loading")
    frame, panels, old, hashes = load()
    hashes[str(HERE/"test_sensitivity.py")] = sha(HERE/"test_sensitivity.py")
    grid, radii, panel_table = [], [], []
    crosschecks = 0
    for panel, ix in panels.items():
        f = frame.iloc[ix]
        n = len(f)
        assert n == int(old.loc[old.panel.eq(panel), "rows"].iloc[0])
        external = bool(f.split.isin(["SG_exposed", "W_new_challenge"]).all())
        bundles = (f.configuration if external else f.group).astype(str).to_numpy()
        sources = (f.split if external else f.source).astype(str).to_numpy()
        assert not f["configuration" if external else "group"].isna().any()
        assert not f["split" if external else "source"].isna().any()
        names, inverse, counts = np.unique(bundles, return_inverse=True, return_counts=True)
        panel_table.append(dict(panel=panel, rows=n, bundles=len(names), source_blocks=len(np.unique(sources))))
        y = f.measured_CD.to_numpy()
        for procedure in PROCEDURES:
            c = f[procedure].to_numpy()
            for baseline in BASELINES:
                b = f[baseline].to_numpy()
                if procedure in PROCEDURES[:2]:
                    archived = old[(old.panel == panel) & (old.candidate == procedure)].iloc[0]
                    mae = np.mean(np.abs(c-y))
                    reduction = 100*(1-mae/np.mean(np.abs(b-y)))
                    np.testing.assert_allclose(mae, archived.mae_CD, rtol=0, atol=1e-12)
                    np.testing.assert_allclose(reduction, archived[baseline+"_improvement_percent"], rtol=0, atol=1e-8)
                    crosschecks += 1
                for weighting in ["row", "equal_bundle"]:
                    w = np.full(n, 1/n) if weighting == "row" else 1/(len(names)*counts[inverse])
                    np.testing.assert_allclose(w.sum(), 1., rtol=0, atol=1e-14)
                    for r in [0., .09]:
                        common = dict(panel=panel, procedure=procedure, baseline=baseline,
                                      weighting=weighting, target_fraction=r, rows=n, bundles=len(names))
                        box = RowBox(b, c, y, w, r)
                        models = {"row_box": box,
                                  "source_shift": SharedShifts(b, c, y, w, r, sources),
                                  "bundle_shift": SharedShifts(b, c, y, w, r, bundles)}
                        box_bounds = [box.bounds(e*1e-4) for e in RADII_COUNTS]
                        for model_name, model in models.items():
                            radii.append(common | dict(uncertainty_model=model_name) | first_zero(model, r))
                            previous_bounds = None
                            for i, e in enumerate(RADII_COUNTS):
                                eps = e*1e-4
                                low, high = model.bounds(eps)
                                observed = box.observed
                                assert low <= high+ATOL_CD
                                assert low >= observed-(2-r)*eps-ATOL_CD
                                assert high <= observed+(2-r)*eps+ATOL_CD
                                assert low >= box_bounds[i][0]-ATOL_CD and high <= box_bounds[i][1]+ATOL_CD
                                if eps == 0:
                                    assert low == high == observed
                                if previous_bounds is not None:
                                    assert low <= previous_bounds[0]+ATOL_CD
                                    assert high >= previous_bounds[1]-ATOL_CD
                                if procedure == baseline and r == 0:
                                    assert low == high == 0
                                minimum_baseline = box.minimum_baseline_mae(eps)
                                grid.append(common | dict(uncertainty_model=model_name, epsilon_drag_counts=e,
                                    epsilon_CD=eps, lower_margin_CD=low, upper_margin_CD=high,
                                    observed_margin_CD=observed,
                                    box_minimum_baseline_mae_CD=minimum_baseline,
                                    percentage_defined_everywhere_sufficient=minimum_baseline > 0,
                                    strict_positive_margin=low > 0))
                                previous_bounds = low, high
        print(f"completed panel {len(panel_table)}/31: {panel}", flush=True)
    assert (len(grid), len(radii), crosschecks) == (23808, 2976, 124)
    for path, digest in hashes.items():
        assert sha(path) == digest, path
    for name, data in [("grid", grid), ("radii", radii), ("panels", panel_table)]:
        pd.DataFrame(data).to_csv(output/(name+".csv"), index=False)
    manifest = dict(status="complete_retrospective_sensitivity_not_prediction_improvement",
        protocol_sha256=PROTOCOL_HASH, runtime_seconds=time.monotonic()-started,
        python=sys.version, numpy=np.__version__, pandas=pd.__version__, platform=platform.platform(),
        longdouble_precision=np.finfo(LD).precision, fixed_CD_tolerance=ATOL_CD,
        radius_tolerance_CD=RADIUS_TOL_CD, grid_rows=len(grid), radius_rows=len(radii),
        panels=len(panels), archived_headline_comparisons=crosschecks, new_fits=0,
        input_sha256=hashes, output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if "sha256" not in k}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new attempt directory; no overwriting evidence")
    try:
        run(args.output)
    except Exception:
        if args.output.exists():
            (args.output/"failure.txt").write_text(traceback.format_exc())
        raise
