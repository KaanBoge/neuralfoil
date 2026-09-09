"""Verify the completed engineering/documentation extension, not new model scores."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FAST = HERE / "engineering/fast_inference"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    output = HERE / "ENGINEERING_DELIVERY_QA.json"
    assert not output.exists(), "Preserve an existing delivery record"
    hashes = {}
    manifests = [(FAST / "artifact_manifest.json", "files"),
                 (FAST / "checked_loader_manifest.json", "files"),
                 (HERE / "publication/verified_claims.json", "input_source_sha256"),
                 (HERE / "engineering/domain_verification.json", "input_code_sha256"),
                 (HERE / "geometry/pre_recovery_hashes.json", "sha256")]
    for path, field in manifests:
        values = read(path)
        for file, expected in values[field].items():
            assert sha(file) == expected, file
            if file in hashes:
                assert hashes[file] == expected
            hashes[file] = expected
        hashes[str(path)] = sha(path)
    audit = read(HERE / "review/fast_inference_audit.json")
    assert audit["status"] == "PASS" and audit["reference_rows_per_label"] == 8868 and audit["labels"] == 3
    assert all(v["same_shape_original_prepared_bit_identical"] for v in audit["same_shape_parity"])
    domain = read(HERE / "engineering/domain_verification.json")
    assert domain["status"] == "PASS"
    assert sum(v["rows"] for v in domain["cohorts"]) == 497
    assert sum(v["eligible"] for v in domain["cohorts"]) == 472
    assert all(v["exact_gate_parity"] for v in domain["cohorts"])
    tests = []
    for cwd, args in [(HERE / "engineering", ["-m", "unittest", "test_domain_contract", "-v"]),
                      (HERE / "validation_plan", ["test_validator.py"]),
                      (HERE / "engineering", ["demo_inference.py"])]:
        result = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        tests.append({"cwd": str(cwd), "args": args, "exit_code": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr})
    spec = importlib.util.spec_from_file_location("extension_freeze_check", HERE / "validation_plan/validate_freeze.py")
    validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    draft = validator.validate(read(HERE / "validation_plan/freeze_manifest.template.json"))
    assert draft["status"].startswith("REFUSED")
    claims = read(HERE / "publication/verified_claims.json")
    card = (HERE / "publication/MODEL_CARD.md").read_text()
    for item in claims["procedures"]:
        for h in item["history"]:
            assert f'{h["xlarge_relative_MAE_reduction_percent"]:.4f}%' in card
        assert f'{item["minimum_of_31_panel_views_against_both_baselines_percent"]:.4f}%'.replace('-', '−') in card
    docs = [HERE / "ENGINEERING_EXTENSION.md", HERE / "publication/MODEL_CARD.md", HERE / "publication/CLAIM_LEDGER.md"]
    checked_links = []
    for doc in docs:
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', doc.read_text()):
            if link.startswith(("https://", "http://", "#")):
                continue
            target = (doc.parent / link).resolve()
            assert target.is_file(), (doc, target)
            checked_links.append(str(target))
    for folder in [HERE / "publication", HERE / "validation_plan", HERE / "engineering"]:
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in [".py", ".md", ".json", ".csv"]:
                hashes[str(path)] = sha(path)
    for path in [Path(__file__), *docs, HERE / "review/fast_inference_audit.py",
                 HERE / "review/fast_inference_audit.json", HERE / "review/RECOVERY_AND_FAST_INFERENCE.md"]:
        hashes[str(path)] = sha(path)
    result = {"status": "PASS_ENGINEERING_EXTENSION_ONLY_GEOMETRY_ACCURACY_ASSESSMENT_PENDING",
              "checks": tests, "unresolved_prospective_template_status": draft["status"],
              "local_links_checked": len(checked_links), "input_artifact_sha256": hashes,
              "warning": "No new accuracy gain, prospective confirmation, deployment, manuscript replacement, or whole-study completion is claimed."}
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ["checks", "input_artifact_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
