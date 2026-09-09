#!/usr/bin/env python3
"""Deterministic semantic and numerical validation for the final manuscript.

The validator reads the rendered-source Markdown and the frozen machine-readable
audit artifacts.  It prints JSON only, uses no randomness, and exits nonzero if
any requirement fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "draft" / "manuscript_final.md"
INFERENCE_JSON = ROOT / "analysis" / "final_inference_audit.json"
SENSITIVITY_JSON = ROOT / "analysis" / "final_sensitivity_metrics.json"
SOURCE_AUDIT_JSON = ROOT / "analysis" / "final_source_method_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def word_count(text: str) -> int:
    """Count whitespace-delimited words, as required by the journal check."""
    return len(text.split())


def lexical_word_count(text: str) -> int:
    """Count words while treating an internal hyphen as part of one word."""
    return len(re.findall(r"\b[\w]+(?:[-\u2013\u2014][\w]+)*\b", text, flags=re.UNICODE))


def expand_citation_group(group: str) -> list[int]:
    values: list[int] = []
    for part in re.split(r"\s*,\s*", group):
        ends = re.split(r"[-\u2013]", part)
        if len(ends) == 1:
            values.append(int(ends[0]))
        else:
            first, last = map(int, ends)
            values.extend(range(first, last + 1))
    return values


def signed(value: float, digits: int) -> str:
    return f"{value:+.{digits}f}" if value >= 0 else f"{value:.{digits}f}"


def contains_all(text: str, tokens: list[str]) -> tuple[bool, list[str]]:
    missing = [token for token in tokens if token not in text]
    return not missing, missing


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, **details: Any) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def select(rows: list[dict[str, Any]], **criteria: Any) -> dict[str, Any]:
    matches = [row for row in rows if all(row.get(key) == value for key, value in criteria.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {criteria!r}, found {len(matches)}")
    return matches[0]


def main() -> int:
    checks: list[dict[str, Any]] = []
    try:
        manuscript = MANUSCRIPT.read_text(encoding="utf-8")
        inference = load_json(INFERENCE_JSON)
        sensitivity = load_json(SENSITIVITY_JSON)
        source_audit = load_json(SOURCE_AUDIT_JSON)

        title_match = re.search(r'^title:\s*"([^"]+)"\s*$', manuscript, flags=re.MULTILINE)
        title = title_match.group(1) if title_match else ""
        title_words = lexical_word_count(title)
        add_check(
            checks,
            "title_word_limit",
            bool(title_match) and title_words <= 12,
            title=title,
            word_count=title_words,
            maximum=12,
        )

        abstract_match = re.search(r"^## Abstract\s*\n+(.+?)(?=\n+\*\*Keywords:)", manuscript, flags=re.MULTILINE | re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else ""
        abstract_paragraphs = [p for p in re.split(r"\n\s*\n", abstract) if p.strip()]
        abstract_words = word_count(abstract)
        add_check(
            checks,
            "abstract_structure_and_length",
            bool(abstract_match) and len(abstract_paragraphs) == 1 and 100 <= abstract_words <= 200,
            paragraph_count=len(abstract_paragraphs),
            whitespace_word_count=abstract_words,
            minimum=100,
            maximum=200,
        )

        first_appearance: list[int] = []
        citation_pattern = re.compile(r"\[((?:\d+(?:[-\u2013]\d+)?)(?:\s*,\s*\d+(?:[-\u2013]\d+)?)*)\]")
        for match in citation_pattern.finditer(manuscript):
            for number in expand_citation_group(match.group(1)):
                if number not in first_appearance:
                    first_appearance.append(number)
        bibliography_numbers = [int(n) for n in re.findall(r"^\[(\d+)\]\s", manuscript, flags=re.MULTILINE)]
        expected_references = list(range(1, 34))
        add_check(
            checks,
            "references_sequential_first_appearance",
            first_appearance == expected_references and bibliography_numbers == expected_references,
            first_appearance=first_appearance,
            bibliography_numbers=bibliography_numbers,
            expected=expected_references,
        )

        figure_pattern = re.compile(
            r"^!\[(Figure\s+(\d+)\.\s+(.+?))\]\(([^)]+)\)(?:\{[^}]+\})?\s*$",
            flags=re.MULTILINE,
        )
        figures: list[dict[str, Any]] = []
        for match in figure_pattern.finditer(manuscript):
            number = int(match.group(2))
            caption = match.group(3).strip()
            relative_path = match.group(4).strip()
            figures.append(
                {
                    "number": number,
                    "caption": caption,
                    "caption_words": lexical_word_count(caption),
                    "path": relative_path,
                    "exists": (ROOT / relative_path).is_file(),
                }
            )
        expected_figures = list(range(1, 12))
        add_check(
            checks,
            "figures_callouts_captions_and_files",
            [item["number"] for item in figures] == expected_figures
            and all(item["caption_words"] <= 25 and item["exists"] for item in figures),
            figures=figures,
            expected_numbers=expected_figures,
            caption_word_maximum=25,
        )

        table_captions = re.findall(r"^\*\*Table\s+([A-F]?\d+)\.\s+.+?\*\*\s*$", manuscript, flags=re.MULTILINE)
        expected_tables = [str(n) for n in range(1, 9)] + ["A1"] + [f"C{n}" for n in range(1, 7)] + ["D1", "E1", "F1"]
        add_check(
            checks,
            "tables_complete_and_unique",
            table_captions == expected_tables,
            captions=table_captions,
            expected=expected_tables,
        )

        equation_tokens = ["Eqs. (1a) and (1b)", "Eq. (2)", "Eq. (3)"]
        equation_ok, equation_missing = contains_all(manuscript, equation_tokens)
        add_check(
            checks,
            "equation_callouts",
            equation_ok,
            required=equation_tokens,
            missing=equation_missing,
        )

        placeholder_patterns = {
            "TODO": r"\bTODO\b",
            "TBD": r"\bTBD\b",
            "FIXME": r"\bFIXME\b",
            "XXX": r"\bXXX\b",
            "placeholder": r"\bplaceholder\b",
            "author_placeholder": r"\[\s*AUTHOR[^\]]*\]",
            "insert_here": r"\binsert\s+here\b",
            "pre_submission_status": r"\bpre[- ]submission\b",
            "internal_status": r"\binternal\s+status\b",
        }
        placeholder_hits = {
            label: len(re.findall(pattern, manuscript, flags=re.IGNORECASE))
            for label, pattern in placeholder_patterns.items()
            if re.search(pattern, manuscript, flags=re.IGNORECASE)
        }
        add_check(checks, "no_placeholders_or_internal_status", not placeholder_hits, hits=placeholder_hits)

        unsupported_hits = re.findall(r"(?<!\d)(?:2,160|2160)(?!\d)", manuscript)
        add_check(
            checks,
            "no_unsupported_2160_probe_claim",
            not unsupported_hits,
            occurrences=len(unsupported_hits),
        )

        attrition = source_audit["neuralfoil_pre_evaluation_attrition"]
        counts = attrition["counts"]
        absent = attrition["group_summaries"]["absent_neuralfoil_output"]
        reached = attrition["group_summaries"]["reached_neuralfoil_output"]
        attrition_tokens = [
            f"parsed {counts['parsed_rows']:,} drag rows",
            f"raw corpus contained {counts['raw_clean_rows']:,} per-row-clean observations",
            f"left {counts['raw_and_name_clean_rows']:,} clean candidates; "
            f"{counts['raw_and_name_clean_absent_rows']:,} rows across "
            f"{counts['raw_and_name_clean_absent_entries']:,} source-airfoil entries had no NeuralFoil output, "
            f"leaving {counts['raw_and_name_clean_reached_rows']:,} evaluated rows",
            f"{round(absent['Re']['mean'], -2):,.0f} versus {round(reached['Re']['mean'], -2):,.0f}",
            f"{absent['CD_meas']['mean']:.5f} versus {reached['CD_meas']['mean']:.5f}",
        ]
        attrition_ok, attrition_missing = contains_all(manuscript, attrition_tokens)
        add_check(
            checks,
            "numeric_attrition_consistency",
            attrition_ok,
            source=str(SOURCE_AUDIT_JSON.relative_to(ROOT)),
            required_renderings=attrition_tokens,
            missing=attrition_missing,
        )

        paired = inference["paired_mean8_minus_xfoil"]
        paired_tokens: list[str] = []
        for outcome, estimate_digits, ci_digits in (("drag", 4, 3), ("lift", 6, 6)):
            row = select(paired, outcome=outcome, bootstrap_specification="source_airfoil_entry")
            paired_tokens.extend(
                [
                    signed(row["estimate"], estimate_digits),
                    signed(row["ci_low"], ci_digits),
                    signed(row["ci_high"], ci_digits),
                ]
            )
        paired_ok, paired_missing = contains_all(manuscript, paired_tokens)
        add_check(
            checks,
            "numeric_paired_pipeline_intervals",
            paired_ok,
            source=str(INFERENCE_JSON.relative_to(ROOT)),
            required_renderings=paired_tokens,
            missing=paired_missing,
        )

        calibration = {row["metric"]: row for row in inference["risk_model_calibration"]}
        calibration_tokens = [
            f"{calibration['calibration_intercept']['estimate']:.4f}",
            f"{calibration['calibration_intercept']['ci_low']:.3f}",
            f"{calibration['calibration_intercept']['ci_high']:.4f}",
            f"{calibration['calibration_slope']['estimate']:.3f}",
            f"{calibration['calibration_slope']['ci_low']:.3f}",
            f"{calibration['calibration_slope']['ci_high']:.3f}",
            f"{calibration['ece_10_fixed_deciles']['estimate']:.4f}",
            f"{calibration['brier_skill']['estimate']:.3f}",
        ]
        entry_full = select(sensitivity["risk_grouping_sensitivity"], group_unit="entry", risk_model="multivariable")
        entry_ablation = select(
            sensitivity["multivariable_no_nominal_geometry"],
            group_unit="entry",
            risk_model="multivariable_no_nominal_geometry",
        )
        no_geometry_tokens = [
            f"{entry_full['auroc']:.5f}",
            f"{entry_ablation['auroc']:.5f}",
            f"{entry_full['average_precision']:.5f}",
            f"{entry_ablation['average_precision']:.5f}",
            f"{entry_full['brier_score']:.5f}",
            f"{entry_ablation['brier_score']:.5f}",
        ]
        risk_tokens = calibration_tokens + no_geometry_tokens
        risk_ok, risk_missing = contains_all(manuscript, risk_tokens)
        add_check(
            checks,
            "numeric_risk_calibration_and_no_geometry_ablation",
            risk_ok,
            sources=[str(INFERENCE_JSON.relative_to(ROOT)), str(SENSITIVITY_JSON.relative_to(ROOT))],
            required_renderings=risk_tokens,
            missing=risk_missing,
        )

        fold_summary = select(
            inference["clean_ridge_fold_assignment_summary"], metric="pooled_paired_change_counts"
        )
        fold_tokens = [
            f"Across {fold_summary['fold_assignments']} airfoil-disjoint fold assignments",
            f"{fold_summary['mean']:.3f}",
            f"{fold_summary['standard_deviation']:.3f}",
            f"{fold_summary['minimum']:.3f}",
            f"{fold_summary['maximum']:.3f}",
        ]
        fold_ok, fold_missing = contains_all(manuscript, fold_tokens)
        add_check(
            checks,
            "numeric_fifty_seed_fold_sensitivity",
            fold_ok and fold_summary["share_below_zero"] == 1.0,
            source=str(INFERENCE_JSON.relative_to(ROOT)),
            required_renderings=fold_tokens,
            missing=fold_missing,
            share_pooled_changes_below_zero=fold_summary["share_below_zero"],
        )

        transfer_tokens: list[str] = []
        for row in inference["clean_ridge_fixed_test_transfer"]:
            transfer_tokens.extend(
                [
                    signed(row["estimate"], 4),
                    signed(row["ci_low"], 3),
                    signed(row["ci_high"], 3),
                ]
            )
        strict_rows = [
            row
            for row in inference["clean_ridge_strict_nominal_airfoil_exclusion"]
            if row["contrast_key"] == "strict_minus_base"
        ]
        for row in strict_rows:
            transfer_tokens.extend(
                [
                    signed(row["estimate"], 4),
                    signed(row["ci_low"], 3),
                    signed(row["ci_high"], 3),
                ]
            )
        transfer_ok, transfer_missing = contains_all(manuscript, transfer_tokens)
        add_check(
            checks,
            "numeric_ordinary_and_strict_transfer",
            transfer_ok and len(strict_rows) == 5,
            source=str(INFERENCE_JSON.relative_to(ROOT)),
            ordinary_rows=len(inference["clean_ridge_fixed_test_transfer"]),
            strict_rows=len(strict_rows),
            required_renderings=transfer_tokens,
            missing=transfer_missing,
        )

        censoring = inference["censoring"]
        all_peak_bias = select(censoring, analysis_set="all_sweeps", quantity="peak_lift_signed_bias")
        all_peak_mae = select(censoring, analysis_set="all_sweeps", quantity="peak_lift_mae")
        all_over = select(censoring, analysis_set="all_sweeps", quantity="peak_lift_overprediction_share")
        all_stall_bias = select(censoring, analysis_set="all_sweeps", quantity="stall_angle_signed_bias")
        all_stall_mae = select(censoring, analysis_set="all_sweeps", quantity="stall_angle_mae")
        censor_tokens = [
            f"Twenty-five of {all_peak_bias['sweeps']} predicted maxima",
            signed(all_peak_bias["lower_bound"], 5),
            f"{all_peak_mae['lower_bound']:.5f}",
            f"{100 * all_over['lower_bound']:.1f}%",
            f"{100 * all_over['upper_bound']:.1f}%",
            signed(all_stall_bias["lower_bound"], 4),
            f"{all_stall_mae['lower_bound']:.4f}",
        ]
        censor_ok, censor_missing = contains_all(manuscript, censor_tokens)
        censor_bounds_valid = all(
            row["upper_bound"] is None
            for row in (all_peak_bias, all_peak_mae, all_stall_bias, all_stall_mae)
        )
        add_check(
            checks,
            "numeric_censoring_bounds",
            censor_ok and censor_bounds_valid,
            source=str(INFERENCE_JSON.relative_to(ROOT)),
            required_renderings=censor_tokens,
            missing=censor_missing,
            finite_upper_bounds_absent=censor_bounds_valid,
        )

        transonic_tokens: list[str] = []
        for source in ("Harris", "TN1546"):
            row = select(inference["transonic_sweep_robustness"], source=source)
            transonic_tokens.extend(
                [
                    row["improved_over_total"],
                    signed(row["median_paired_change_counts"], 2),
                    str(row["sweeps"]),
                ]
            )
        transonic_ok, transonic_missing = contains_all(manuscript, transonic_tokens)
        add_check(
            checks,
            "numeric_transonic_sweep_counts",
            transonic_ok,
            source=str(INFERENCE_JSON.relative_to(ROOT)),
            required_renderings=transonic_tokens,
            missing=transonic_missing,
        )

        absence = sensitivity["xfoil_absence_composite_sensitivity"]
        absence_tokens = [
            f"{absence['xfoil_absent_conditions']:,} absent outputs",
            f"{absence['xfoil_best_case_zero_absent_penalty_mae_counts']:.3f}",
            f"{absence['neuralfoil_mean8_all_condition_mae_counts']:.3f}",
            f"{absence['break_even_mean_absent_penalty_counts']:.3f} counts per absent output",
        ]
        absence_ok, absence_missing = contains_all(manuscript, absence_tokens)
        add_check(
            checks,
            "numeric_xfoil_absence_composite",
            absence_ok
            and absence["eligible_unique_conditions"]
            == absence["xfoil_returned_conditions"] + absence["xfoil_absent_conditions"],
            source=str(SENSITIVITY_JSON.relative_to(ROOT)),
            required_renderings=absence_tokens,
            missing=absence_missing,
            arithmetic_identity=(
                f"{absence['eligible_unique_conditions']}="
                f"{absence['xfoil_returned_conditions']}+{absence['xfoil_absent_conditions']}"
            ),
        )

        passed = all(check["passed"] for check in checks)
        result = {
            "schema_version": 1,
            "validator": str(Path(__file__).resolve().relative_to(ROOT)),
            "manuscript": str(MANUSCRIPT.relative_to(ROOT)),
            "status": "pass" if passed else "fail",
            "checks_passed": sum(check["passed"] for check in checks),
            "checks_total": len(checks),
            "checks": checks,
        }
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0 if passed else 1
    except Exception as exc:  # Preserve strict JSON even for malformed/missing artifacts.
        result = {
            "schema_version": 1,
            "validator": str(Path(__file__).resolve().relative_to(ROOT)),
            "manuscript": str(MANUSCRIPT.relative_to(ROOT)),
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "checks_completed": checks,
        }
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
