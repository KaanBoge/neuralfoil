"""Replay only existing input/gate columns, not measured experimental labels."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from domain_contract import legacy_benchmark_gate

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RISK = PROJECT / "model_development_20260907_risk_policy"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    path = HERE / "domain_verification.json"
    assert not path.exists(), "Preserve an existing verification record"
    witness = RISK / "assessment/report.json"
    prior = json.loads(witness.read_text())["input_source_sha256"]
    hashes = {str(witness): sha(witness)}
    rows = []
    for cohort, total, eligible in [("SG_exposed", 242, 234), ("W_new_challenge", 255, 238)]:
        source = RISK / "exposed_results" / f"{cohort}_predictions.csv"
        assert sha(source) == prior[str(source)]
        hashes[str(source)] = prior[str(source)]
        f = pd.read_csv(source, usecols=["alpha", "Re", "thickness_ratio", "mean8_CD", "inference_gate"])
        actual = legacy_benchmark_gate(f.alpha, f.Re, f.thickness_ratio, f.mean8_CD)
        assert all(str(v).lower() in ["true", "false"] for v in f.inference_gate)
        expected = np.array([str(v).lower() == "true" for v in f.inference_gate], dtype=bool)
        np.testing.assert_array_equal(actual, expected)
        assert len(f) == total and actual.sum() == eligible
        rows.append({"cohort": cohort, "rows": total, "eligible": eligible,
                     "fallback": total - eligible, "exact_gate_parity": True})
    for name in ["domain_contract.py", "test_domain_contract.py", "verify_domain.py"]:
        p = HERE / name; hashes[str(p)] = sha(p)
    result = {"status": "PASS", "cohorts": rows, "input_code_sha256": hashes,
              "warning": "Legacy numerical eligibility only, not a physical-validity or accuracy guarantee. No measured-label column loaded."}
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "input_code_sha256"}, indent=2))


if __name__ == "__main__":
    main()
