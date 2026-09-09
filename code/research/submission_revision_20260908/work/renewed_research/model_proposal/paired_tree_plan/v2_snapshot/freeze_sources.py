"""Metadata/source freeze only: never reads or materializes the model NPZ."""
from pathlib import Path
import support as s

FILES=('PLAN.md','SCHEMA.md','support.py','producer.py','runner.py','fixtures.py','test_producer.py','verify_synthetic.py','freeze_sources.py','IMPLEMENTATION.md')

def main():
    deps={rel:pin for rel,pin in s.PINS.values()}
    deps.update({
      'feature_relation_certification/PAIRED_TREE_ENCLOSURE_PLAN.md':'9b5d86a8d616c28bac1575504f311151d8089faaf6b5f7dbc54137010b349c44',
      'uncertainty_review/range_bound_feasibility/PAIRED_ENCLOSURE_REVIEW.md':'ed01ee091119f59b6f0a02a9d7caded2add6f5cab096a8cd79058d62ef36a2e7',
      'uncertainty_review/range_bound_feasibility/paired_checker.py':'e3d575e59bb402e67add6114d42a1c0860a91bde2e2f694d0c53693ba7faaec7',
      'tree_range_refinement/feature_relation_oracle_review/oracle.py':'e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11',
      s.MANIFEST:s.MANIFEST_SHA,s.STAGE0:s.STAGE0_SHA})
    ledger=[]
    for rel in ('uncertainty_review/range_bound_feasibility/PAIRED_CHECKER_HANDOFF.md',
                'uncertainty_review/range_bound_feasibility/PAIRED_SYNTHETIC_GATE.json',
                'uncertainty_review/range_bound_feasibility/test_paired_checker.py'):
        deps[rel]=s.digest(s.safe_path(s.ROOT/rel).read_bytes())
    for rel,pin in deps.items():s.read_pinned(s.ROOT/rel,pin,ledger,'metadata_or_source_freeze')
    sources={name:s.digest(s.safe_path(s.HERE/name).read_bytes()) for name in FILES}
    evidence={str(p.relative_to(s.HERE)):s.digest(p.read_bytes()) for p in sorted((s.HERE/'synthetic_attempt_1').iterdir()) if p.name!='certificate.json.partial'}
    reg={'schema':'PAIRED_TREE_SOURCE_REGISTRY_V1','sources':sources,'dependencies':deps,
         'input':{'path':s.MODEL,'sha256':s.MODEL_SHA,'members':list(s.MEMBERS)},
         'scope':{'context':'final','branch':'proper','family':'capped','stages':400,'dimensions':62,'domains':['D','R']},
         'synthetic_evidence':evidence,'real_execution_authorized':False,
         'freeze_model_members_materialized':0,'read_ledger':ledger}
    print(s.exclusive(s.HERE/'REGISTRY.json',reg))

if __name__=='__main__':main()
