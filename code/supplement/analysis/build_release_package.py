from __future__ import annotations

"""Build deterministic project and clean-release SHA-256 manifests.

The release intentionally omits row-level third-party or derived performance
records. It includes aggregate audit products and points to the frozen source
repository for full reanalysis under the applicable upstream terms.
"""

import csv
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_MANIFEST = ROOT / "analysis" / "reproducibility_manifest.csv"
RELEASE_ROOT = ROOT / "output" / "release" / "NeuralFoil_Journal_Final"

ROOT_DOCUMENTS = [
    "AUTHOR_INPUT_REQUIRED.md",
    "RELEASE_README.md",
    "REPRODUCIBILITY.md",
    "SUBMISSION_CHECKLIST.md",
    "THIRD_PARTY_DATA_NOTICE.md",
]

RELEASE_ANALYSIS = [
    "airfoil_level_win_rates.csv",
    "all_model_sizes_accuracy_speed.csv",
    "analysis_snapshot_manifest.csv",
    "analyze_study.py",
    "build_final_manuscript.py",
    "build_release_package.py",
    "claim_evidence_matrix.csv",
    "clean_only_correction_audit.py",
    "cohort_flow.csv",
    "common_distribution_and_bias.csv",
    "confidence_deciles.csv",
    "duplicate_condition_sensitivity.csv",
    "extended_analysis.py",
    "final_inference_audit.json",
    "final_inference_audit.py",
    "final_inference_censoring.csv",
    "final_inference_clean_ridge_fold_sensitivity.csv",
    "final_inference_clean_ridge_fold_sensitivity_summary.csv",
    "final_inference_clean_ridge_strict_transfer.csv",
    "final_inference_clean_ridge_transfer.csv",
    "final_inference_model_size_rank.csv",
    "final_inference_paired_bootstrap.csv",
    "final_inference_risk_calibration.csv",
    "final_inference_transonic_sweeps.csv",
    "final_sensitivity_analysis.py",
    "final_sensitivity_metrics.json",
    "final_source_method_audit.csv",
    "final_source_method_audit.json",
    "final_source_method_audit.py",
    "grouping_sensitivity.csv",
    "measurement_variability_proxy.csv",
    "post_audit_clean_v1_metrics.json",
    "post_audit_clean_v1_summary.csv",
    "postprocess_docx.py",
    "recovery_sources.csv",
    "reynolds_error_map_verified.csv",
    "requirements-final.txt",
    "risk_airfoil_split_sensitivity.csv",
    "risk_grouping_sensitivity.csv",
    "risk_model_calibration.csv",
    "risk_model_selective_curve.csv",
    "risk_of_bias.csv",
    "risk_threshold_sensitivity.csv",
    "risk_triage_strata.csv",
    "source_specific_head_to_head.csv",
    "spread_deciles_corrected.csv",
    "stall_censoring_sensitivity.csv",
    "transonic_candidates.csv",
    "transonic_holdout_summary.csv",
    "validate_final_manuscript.py",
    "verified_metrics.json",
    "verified_metrics_extended.json",
    "weighting_sensitivity.csv",
    "xfoil_absence_composite_sensitivity.csv",
    "xfoil_availability_by_alpha.csv",
    "xfoil_availability_by_re.csv",
    "xfoil_availability_by_re_extended.csv",
    "xfoil_availability_by_source.csv",
    "xfoil_selection_audit.csv",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(path: Path, files: list[Path], *, relative_to: Path) -> None:
    rows = []
    for file_path in sorted(files, key=lambda item: item.relative_to(relative_to).as_posix()):
        rel = file_path.relative_to(relative_to).as_posix()
        top = rel.split("/", 1)[0]
        rows.append(
            {
                "path": rel,
                "bytes": file_path.stat().st_size,
                "sha256": sha256_file(file_path),
                "category": top,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256", "category"])
        writer.writeheader()
        writer.writerows(rows)


def project_files() -> list[Path]:
    files: list[Path] = []
    for relative in ROOT_DOCUMENTS:
        files.append(ROOT / relative)
    for folder in ("analysis", "draft", "figures", "source"):
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if ".git" in rel.parts or "__pycache__" in rel.parts:
                continue
            if path == PROJECT_MANIFEST:
                continue
            files.append(path)
    files.extend(
        [
            ROOT / "output" / "docx" / "NeuralFoil_Journal_Manuscript_Final.docx",
            ROOT / "output" / "pdf" / "NeuralFoil_Journal_Manuscript_Final.pdf",
        ]
    )
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing project-manifest inputs:\n" + "\n".join(missing))
    unique = {path.resolve(): path for path in files}
    return list(unique.values())


def release_mapping() -> dict[Path, Path]:
    mapping: dict[Path, Path] = {}
    for relative in ROOT_DOCUMENTS:
        destination_name = "README.md" if relative == "RELEASE_README.md" else relative
        mapping[ROOT / relative] = Path(destination_name)
    mapping[ROOT / "draft" / "manuscript_final.md"] = Path("manuscript_final.md")
    mapping[
        ROOT / "output" / "docx" / "NeuralFoil_Journal_Manuscript_Final.docx"
    ] = Path("NeuralFoil_Journal_Manuscript_Final.docx")
    mapping[
        ROOT / "output" / "pdf" / "NeuralFoil_Journal_Manuscript_Final.pdf"
    ] = Path("NeuralFoil_Journal_Manuscript_Final.pdf")
    mapping[PROJECT_MANIFEST] = Path("analysis") / PROJECT_MANIFEST.name
    for name in RELEASE_ANALYSIS:
        mapping[ROOT / "analysis" / name] = Path("analysis") / name
    for figure in sorted((ROOT / "figures").glob("figure_*.png")):
        mapping[figure] = Path("figures") / figure.name
    return mapping


def build_release() -> None:
    files = project_files()
    write_manifest(PROJECT_MANIFEST, files, relative_to=ROOT)

    mapping = release_mapping()
    missing = [str(source) for source in mapping if not source.is_file()]
    if missing:
        raise FileNotFoundError("Missing release inputs:\n" + "\n".join(missing))

    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    for source, relative_destination in mapping.items():
        destination = RELEASE_ROOT / relative_destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    checksum_path = RELEASE_ROOT / "SHA256SUMS.csv"
    allowed = {relative.as_posix() for relative in mapping.values()} | {checksum_path.name}
    observed = {
        path.relative_to(RELEASE_ROOT).as_posix()
        for path in RELEASE_ROOT.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(observed - allowed)
    if unexpected:
        raise RuntimeError(
            "Release contains unexpected stale files; remove them explicitly before rebuilding:\n"
            + "\n".join(unexpected)
        )

    release_files = [
        path for path in RELEASE_ROOT.rglob("*") if path.is_file() and path != checksum_path
    ]
    write_manifest(checksum_path, release_files, relative_to=RELEASE_ROOT)
    print(f"Project manifest: {PROJECT_MANIFEST}")
    print(f"Release: {RELEASE_ROOT}")
    print(f"Release files excluding checksum: {len(release_files)}")
    print(f"Release checksum SHA-256: {sha256_file(checksum_path)}")


if __name__ == "__main__":
    build_release()
