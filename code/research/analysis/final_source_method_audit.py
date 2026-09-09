from __future__ import annotations

"""Deterministic source/method audit for the final NeuralFoil manuscript.

This script uses only the Python standard library. It records three narrowly
defined checks that can be regenerated from the archived repository:

1. attrition between the parsed LSAT corpus and the saved NeuralFoil output;
2. the different geometry preprocessing paths used for NeuralFoil and XFOIL;
3. the archive status of the numerical software-probe claims.

The output is intentionally descriptive. It does not infer the error of rows
without NeuralFoil output and does not claim that XFOIL received literally
unmodified coordinates: XFOIL's PANE command performs its own repaneling.
"""

import ast
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "source" / "neuralfoil_repo"
STUDY = REPO / "study"
DATA = STUDY / "data"
TOOLS = STUDY / "tools"
OUT_JSON = ROOT / "analysis" / "final_source_method_audit.json"
OUT_CSV = ROOT / "analysis" / "final_source_method_audit.csv"

CORPUS_PATH = DATA / "lsat-corpus.csv"
NF_PATH = DATA / "lsat-nf.csv"
GEOM_SCRIPT = TOOLS / "lsat_geom.py"
NF_SCRIPT = TOOLS / "lsat_run.py"
XFOIL_SCRIPT = TOOLS / "lsat_xfoil.py"
PROBE_SCRIPT = TOOLS / "probes.py"
PARITY_SCRIPT = TOOLS / "parity.py"
CLAIM_MATRIX = ROOT / "analysis" / "claim_evidence_matrix.csv"
MANUSCRIPT = ROOT / "draft" / "manuscript_extended.md"
SOURCE_NARRATIVE = DATA / "research-answer.md"

EXPECTED = {
    "parsed_rows": 14_773,
    "neuralfoil_output_rows": 13_394,
    "raw_clean_rows": 12_664,
    "raw_clean_reached_rows": 11_439,
    "raw_clean_absent_rows": 1_225,
    "raw_and_name_clean_rows": 9_664,
    "raw_and_name_clean_reached_rows": 8_653,
    "raw_and_name_clean_absent_rows": 1_011,
    "raw_and_name_clean_reached_entries": 135,
    "raw_and_name_clean_absent_entries": 18,
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rounded_number(value: str, digits: int) -> float:
    return round(float(value), digits)


def corpus_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        row["source"],
        row["airfoil"],
        rounded_number(row["Re"], 3),
        rounded_number(row["alpha"], 4),
        rounded_number(row["CL"], 5),
        rounded_number(row["CD"], 6),
    )


def neuralfoil_key(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        row["source"],
        row["airfoil"],
        rounded_number(row["Re"], 3),
        rounded_number(row["alpha"], 4),
        rounded_number(row["CL_meas"], 5),
        rounded_number(row["CD_meas"], 6),
    )


def extract_mod_tokens() -> tuple[str, ...]:
    tree = ast.parse(GEOM_SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MOD_TOKENS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, tuple) or not all(isinstance(v, str) for v in value):
                raise AssertionError("lsat_geom.py MOD_TOKENS is not a literal string tuple")
            return value
    raise AssertionError("MOD_TOKENS was not found in lsat_geom.py")


def name_configuration(name: str, mod_tokens: tuple[str, ...]) -> str:
    lowered = name.lower()
    if "flat plate" in lowered:
        return "plate"
    return "modified" if any(token in lowered for token in mod_tokens) else "clean"


def add_occurrence_keys(
    rows: Iterable[dict[str, str]],
    key_function: Any,
) -> list[tuple[dict[str, str], tuple[Any, ...]]]:
    counts: Counter[tuple[Any, ...]] = Counter()
    output = []
    for row in rows:
        base = key_function(row)
        occurrence = counts[base]
        counts[base] += 1
        output.append((row, (*base, occurrence)))
    return output


def finite_summary(values: Iterable[float]) -> dict[str, float | int]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {"count": 0}
    return {
        "count": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "minimum": min(clean),
        "maximum": max(clean),
    }


def line_evidence(path: Path, needle: str, interpretation: str) -> dict[str, Any]:
    hits = [
        (index, line.rstrip())
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in line
    ]
    if len(hits) != 1:
        raise AssertionError(f"Expected one occurrence of {needle!r} in {rel(path)}, found {len(hits)}")
    line_number, text = hits[0]
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "line": line_number,
        "text": text.strip(),
        "interpretation": interpretation,
    }


def literal_print_section_labels(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    labels = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "print" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            match = re.match(r"^([A-Z])\.\s", first.value)
            if match:
                labels.append(match.group(1))
    return sorted(set(labels))


def find_text_line(path: Path, needle: str) -> dict[str, Any]:
    hits = [
        (index, line.strip())
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in line
    ]
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "needle": needle,
        "matches": [{"line": line, "text": text} for line, text in hits],
    }


def build_audit() -> dict[str, Any]:
    corpus = read_csv(CORPUS_PATH)
    neuralfoil = read_csv(NF_PATH)
    mod_tokens = extract_mod_tokens()

    corpus_occurrences = add_occurrence_keys(corpus, corpus_key)
    neuralfoil_occurrences = add_occurrence_keys(neuralfoil, neuralfoil_key)
    neuralfoil_keys = {key for _, key in neuralfoil_occurrences}
    if len(neuralfoil_keys) != len(neuralfoil_occurrences):
        raise AssertionError("NeuralFoil occurrence keys are not unique")

    reached_rows = []
    absent_rows = []
    for row, key in corpus_occurrences:
        enriched = dict(row)
        enriched["entry"] = f'{row["source"]}|{row["airfoil"]}'
        enriched["name_configuration"] = name_configuration(row["airfoil"], mod_tokens)
        enriched["reached_neuralfoil_output"] = key in neuralfoil_keys
        (reached_rows if enriched["reached_neuralfoil_output"] else absent_rows).append(enriched)

    matched_keys = {key for _, key in corpus_occurrences} & neuralfoil_keys
    unmatched_nf_keys = neuralfoil_keys - {key for _, key in corpus_occurrences}
    if unmatched_nf_keys:
        raise AssertionError(f"{len(unmatched_nf_keys)} NeuralFoil rows do not map to the corpus")
    if len(matched_keys) != len(neuralfoil):
        raise AssertionError("Not every NeuralFoil output row maps exactly once to the corpus")

    raw_clean = [row for row, _ in corpus_occurrences if row["config"] == "clean"]
    raw_clean_reached = [row for row in reached_rows if row["config"] == "clean"]
    raw_clean_absent = [row for row in absent_rows if row["config"] == "clean"]
    rule_clean = [
        row
        for row in reached_rows + absent_rows
        if row["config"] == "clean" and row["name_configuration"] == "clean"
    ]
    rule_clean_reached = [row for row in rule_clean if row["reached_neuralfoil_output"]]
    rule_clean_absent = [row for row in rule_clean if not row["reached_neuralfoil_output"]]

    attrition_counts = {
        "parsed_rows": len(corpus),
        "neuralfoil_output_rows": len(neuralfoil),
        "raw_clean_rows": len(raw_clean),
        "raw_clean_reached_rows": len(raw_clean_reached),
        "raw_clean_absent_rows": len(raw_clean_absent),
        "raw_and_name_clean_rows": len(rule_clean),
        "raw_and_name_clean_reached_rows": len(rule_clean_reached),
        "raw_and_name_clean_absent_rows": len(rule_clean_absent),
        "raw_and_name_clean_reached_entries": len({row["entry"] for row in rule_clean_reached}),
        "raw_and_name_clean_absent_entries": len({row["entry"] for row in rule_clean_absent}),
    }
    if attrition_counts != EXPECTED:
        raise AssertionError(
            "Source-method audit counts changed:\n"
            + json.dumps({"expected": EXPECTED, "observed": attrition_counts}, indent=2, sort_keys=True)
        )

    attrition_summary = {}
    for label, rows in [
        ("reached_neuralfoil_output", rule_clean_reached),
        ("absent_neuralfoil_output", rule_clean_absent),
    ]:
        attrition_summary[label] = {
            "rows": len(rows),
            "entries": len({row["entry"] for row in rows}),
            "source_rows": dict(sorted(Counter(row["source"] for row in rows).items())),
            "Re": finite_summary(float(row["Re"]) for row in rows),
            "alpha_deg": finite_summary(float(row["alpha"]) for row in rows),
            "CL_meas": finite_summary(float(row["CL"]) for row in rows),
            "CD_meas": finite_summary(float(row["CD"]) for row in rows),
        }

    missing_entry_rows: dict[tuple[str, str], int] = defaultdict(int)
    for row in rule_clean_absent:
        missing_entry_rows[(row["source"], row["airfoil"])] += 1
    missing_entries = [
        {"source": source, "airfoil": airfoil, "rows": rows}
        for (source, airfoil), rows in sorted(
            missing_entry_rows.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]

    geometry_evidence = {
        "different_preprocessing_paths": True,
        "neuralfoil_path": "normalized coordinates -> AeroSandbox Airfoil -> Kulfan conversion -> NeuralFoil",
        "xfoil_path": "normalized coordinates -> coordinate file -> XFOIL LOAD/PANE -> XFOIL",
        "qualification": "PANE repanels the coordinate-file geometry; this audit does not call the XFOIL path unmodified.",
        "evidence": [
            line_evidence(
                NF_SCRIPT,
                ".to_kulfan_airfoil()",
                "NeuralFoil receives an AeroSandbox Kulfan conversion of the loaded coordinates.",
            ),
            line_evidence(
                XFOIL_SCRIPT,
                'pts = load_pts(GEO[key]["path"])',
                "The XFOIL path begins from the normalized coordinate points.",
            ),
            line_evidence(
                XFOIL_SCRIPT,
                'f.write(f" {x:.6f} {y:.6f}\\n")',
                "Those points are serialized to the XFOIL coordinate file.",
            ),
            line_evidence(
                XFOIL_SCRIPT,
                "PANE\\nOPER",
                "XFOIL loads and repanels that coordinate file before analysis.",
            ),
        ],
    }

    printed_probe_sections = literal_print_section_labels(PROBE_SCRIPT)
    expected_probe_input = STUDY / "uiuc-airfoils.json"
    dedicated_probe_outputs = sorted(
        rel(path)
        for path in STUDY.rglob("*")
        if path.is_file()
        and re.match(r"^(probes?|parity).*(?:txt|json|csv|log)$", path.name, flags=re.IGNORECASE)
    )
    if printed_probe_sections != ["B", "C", "D"]:
        raise AssertionError(f"Unexpected executable probe section labels: {printed_probe_sections}")
    if expected_probe_input.exists():
        raise AssertionError("Previously absent uiuc-airfoils.json is now present; update this audit")
    if dedicated_probe_outputs:
        raise AssertionError(f"Dedicated probe outputs now exist; update this audit: {dedicated_probe_outputs}")

    claim_rows = read_csv(CLAIM_MATRIX)
    software_claims = [row for row in claim_rows if row.get("claim") == "Software probes"]
    if len(software_claims) != 1:
        raise AssertionError(f"Expected one Software probes row, found {len(software_claims)}")

    probe_inventory = {
        "probe_script": rel(PROBE_SCRIPT),
        "probe_script_sha256": sha256(PROBE_SCRIPT),
        "probe_script_executable_section_labels": printed_probe_sections,
        "hard_wrongs_section_declared_in_docstring": "A. HARD WRONGS" in PROBE_SCRIPT.read_text(encoding="utf-8"),
        "hard_wrongs_executable_section_present": "A" in printed_probe_sections,
        "required_probe_input": rel(expected_probe_input),
        "required_probe_input_present": expected_probe_input.exists(),
        "dedicated_probe_or_parity_output_artifacts": dedicated_probe_outputs,
        "parity_script": rel(PARITY_SCRIPT),
        "parity_script_sha256": sha256(PARITY_SCRIPT),
        "claim_matrix_software_probe_row": software_claims[0],
        "claim_matrix_sha256": sha256(CLAIM_MATRIX),
        "manuscript_claim_location": find_text_line(MANUSCRIPT, "2,160 prespecified extreme-condition probes"),
        "source_narrative_claim_location": find_text_line(SOURCE_NARRATIVE, "2,160 conditions"),
        "audit_conclusion": (
            "The archive contains probe/parity scripts and narrative claims, but no dedicated result artifact; "
            "probes.py lacks an executable A section and its uiuc-airfoils.json input is absent."
        ),
    }

    hashed_inputs = [
        CORPUS_PATH,
        NF_PATH,
        GEOM_SCRIPT,
        NF_SCRIPT,
        XFOIL_SCRIPT,
        PROBE_SCRIPT,
        PARITY_SCRIPT,
        CLAIM_MATRIX,
        MANUSCRIPT,
        SOURCE_NARRATIVE,
    ]
    return {
        "schema_version": 2,
        "audit_status": "deterministic source/method audit; descriptive, not causal",
        "audit_script": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "inputs": [
            {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in hashed_inputs
        ],
        "assertions": [
            {
                "id": "neuralfoil_rows_map_one_to_one_to_corpus",
                "status": "pass",
                "observed": len(matched_keys),
                "expected": len(neuralfoil),
            },
            {
                "id": "archived_attrition_counts_match_frozen_expectations",
                "status": "pass",
                "observed": attrition_counts,
                "expected": EXPECTED,
            },
            {
                "id": "geometry_preprocessing_evidence_lines_are_unique",
                "status": "pass",
                "observed": len(geometry_evidence["evidence"]),
                "expected": 4,
            },
            {
                "id": "probe_executable_sections_are_B_C_D_only",
                "status": "pass",
                "observed": printed_probe_sections,
                "expected": ["B", "C", "D"],
            },
            {
                "id": "required_probe_input_is_absent",
                "status": "pass",
                "observed": expected_probe_input.exists(),
                "expected": False,
            },
            {
                "id": "dedicated_probe_result_artifact_is_absent",
                "status": "pass",
                "observed": dedicated_probe_outputs,
                "expected": [],
            },
        ],
        "neuralfoil_pre_evaluation_attrition": {
            "matching_key": [
                "source",
                "airfoil",
                "Re rounded to 0.001",
                "alpha rounded to 0.0001 deg",
                "CL rounded to 0.00001",
                "CD rounded to 0.000001",
                "occurrence index within exact rounded key",
            ],
            "name_configuration_rule_source": rel(GEOM_SCRIPT),
            "name_configuration_mod_tokens": list(mod_tokens),
            "counts": attrition_counts,
            "absent_share_of_raw_and_name_clean": (
                attrition_counts["raw_and_name_clean_absent_rows"]
                / attrition_counts["raw_and_name_clean_rows"]
            ),
            "group_summaries": attrition_summary,
            "absent_entries": missing_entries,
            "interpretation": (
                "Rows without saved NeuralFoil output are outside the evaluated 8,653-row cohort. "
                "The archive does not support imputing their NeuralFoil error or a causal failure type."
            ),
        },
        "geometry_preprocessing": geometry_evidence,
        "probe_artifact_inventory": probe_inventory,
    }


def flatten_csv_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, artifact in [
        ("audit_script", audit["audit_script"]),
        *(("input", item) for item in audit["inputs"]),
    ]:
        rows.append(
            {
                "record_type": "artifact_hash",
                "group": group,
                "metric": artifact["path"],
                "value": artifact["sha256"],
                "units": "sha256",
                "source_path": artifact["path"],
                "detail": (
                    f'{artifact["bytes"]} bytes' if "bytes" in artifact else "audit generator source"
                ),
            }
        )
    for assertion in audit["assertions"]:
        rows.append(
            {
                "record_type": "assertion",
                "group": assertion["status"],
                "metric": assertion["id"],
                "value": json.dumps(assertion["observed"], sort_keys=True, allow_nan=False),
                "units": "test_result",
                "source_path": rel(Path(__file__).resolve()),
                "detail": "expected="
                + json.dumps(assertion["expected"], sort_keys=True, allow_nan=False),
            }
        )
    attrition = audit["neuralfoil_pre_evaluation_attrition"]
    for metric, value in attrition["counts"].items():
        rows.append(
            {
                "record_type": "attrition_count",
                "group": "all",
                "metric": metric,
                "value": value,
                "units": "rows" if not metric.endswith("entries") else "entries",
                "source_path": f"{rel(CORPUS_PATH)};{rel(NF_PATH)}",
                "detail": "one-to-one occurrence-key audit",
            }
        )
    rows.append(
        {
            "record_type": "attrition_rate",
            "group": "raw_and_name_clean",
            "metric": "absent_share_of_raw_and_name_clean",
            "value": attrition["absent_share_of_raw_and_name_clean"],
            "units": "fraction",
            "source_path": f"{rel(CORPUS_PATH)};{rel(NF_PATH)};{rel(GEOM_SCRIPT)}",
            "detail": "absence from saved NeuralFoil outputs; not a causal failure classification",
        }
    )
    for group, summary in attrition["group_summaries"].items():
        for variable in ["Re", "alpha_deg", "CL_meas", "CD_meas"]:
            for statistic, value in summary[variable].items():
                rows.append(
                    {
                        "record_type": "attrition_summary",
                        "group": group,
                        "metric": f"{variable}_{statistic}",
                        "value": value,
                        "units": {
                            "Re": "dimensionless",
                            "alpha_deg": "deg",
                            "CL_meas": "dimensionless",
                            "CD_meas": "dimensionless",
                        }[variable],
                        "source_path": f"{rel(CORPUS_PATH)};{rel(NF_PATH)}",
                        "detail": "raw-and-name-clean rows under archived lsat_geom.py token rule",
                    }
                )
        for source, count in summary["source_rows"].items():
            rows.append(
                {
                    "record_type": "attrition_source_count",
                    "group": group,
                    "metric": f"source_{source}_rows",
                    "value": count,
                    "units": "rows",
                    "source_path": f"{rel(CORPUS_PATH)};{rel(NF_PATH)}",
                    "detail": "raw-and-name-clean rows under archived lsat_geom.py token rule",
                }
            )
    for item in attrition["absent_entries"]:
        rows.append(
            {
                "record_type": "absent_entry",
                "group": item["source"],
                "metric": item["airfoil"],
                "value": item["rows"],
                "units": "rows",
                "source_path": rel(CORPUS_PATH),
                "detail": "raw-and-name-clean entry absent from saved NeuralFoil output",
            }
        )
    for item in audit["geometry_preprocessing"]["evidence"]:
        rows.append(
            {
                "record_type": "geometry_code_evidence",
                "group": "NeuralFoil" if item["path"] == rel(NF_SCRIPT) else "XFOIL",
                "metric": f'line_{item["line"]}',
                "value": item["text"],
                "units": "source_code",
                "source_path": item["path"],
                "detail": item["interpretation"],
            }
        )
    probe = audit["probe_artifact_inventory"]
    for metric, value, detail in [
        (
            "hard_wrongs_executable_section_present",
            probe["hard_wrongs_executable_section_present"],
            "Docstring declares A. HARD WRONGS, but executable print sections are B/C/D.",
        ),
        (
            "required_probe_input_present",
            probe["required_probe_input_present"],
            probe["required_probe_input"],
        ),
        (
            "dedicated_probe_or_parity_output_artifact_count",
            len(probe["dedicated_probe_or_parity_output_artifacts"]),
            "Dedicated filename search under source/neuralfoil_repo/study.",
        ),
    ]:
        rows.append(
            {
                "record_type": "probe_artifact_inventory",
                "group": "software_probes",
                "metric": metric,
                "value": value,
                "units": "boolean" if isinstance(value, bool) else "files",
                "source_path": rel(PROBE_SCRIPT),
                "detail": detail,
            }
        )
    return rows


def write_outputs(audit: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    rows = flatten_csv_rows(audit)
    fieldnames = ["record_type", "group", "metric", "value", "units", "source_path", "detail"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    audit = build_audit()
    write_outputs(audit)
    print(json.dumps({
        "json": rel(OUT_JSON),
        "csv": rel(OUT_CSV),
        "counts": audit["neuralfoil_pre_evaluation_attrition"]["counts"],
        "different_geometry_preprocessing": audit["geometry_preprocessing"]["different_preprocessing_paths"],
        "probe_artifact_inventory": {
            "hard_wrongs_executable_section_present": audit["probe_artifact_inventory"]["hard_wrongs_executable_section_present"],
            "required_probe_input_present": audit["probe_artifact_inventory"]["required_probe_input_present"],
            "dedicated_output_artifact_count": len(
                audit["probe_artifact_inventory"]["dedicated_probe_or_parity_output_artifacts"]
            ),
        },
    }, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
