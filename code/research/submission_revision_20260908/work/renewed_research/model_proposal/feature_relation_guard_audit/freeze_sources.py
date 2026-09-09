"""Source-only freeze; no scientific payload is read or materialized."""
import json
from pathlib import Path
import audit as a
def main():
    a.checked(a.REL,a.REL_SHA);a.checked(a.PLAN,a.PLAN_SHA)
    names=['audit.py','test_audit.py','freeze_sources.py','README.md']
    result={'status':'SOURCE_ONLY_PENDING_REVIEW_AND_EXECUTION_APPROVAL',
        'source_sha256':{n:a.sha((a.HERE/n).read_bytes()) for n in names},
        'plan_sha256':a.PLAN_SHA,'relations_sha256':a.REL_SHA,'manifest_sha256':a.MANIFEST_SHA,
        'parent_archive_sha256':a.ZIP_SHA,'fixed_payloads':a.PINS,'synthetic_tests':14,
        'actual_feature_materializations':0,'new_fits':0}
    a.write_json(a.HERE/'IMPLEMENTATION_FREEZE.json',result)
    print(a.sha((a.HERE/'IMPLEMENTATION_FREEZE.json').read_bytes()))
if __name__=='__main__':main()
