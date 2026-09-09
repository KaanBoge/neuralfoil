"""Print an unauthorized, finite metadata/source-only approval proposal."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[4]
R='submission_revision_20260908/work/renewed_research/'
P=R+'uncertainty_review/package_v6_plan/'
F=R+'independent_environment/final_qa_tools/'
V='submission_revision_20260908/renewed_manuscript_v9/'
def digest(n):
    p=PROJECT/n
    if any(x.is_symlink() for x in [p,*p.parents]) or not p.is_file() or p.stat().st_size>16*1024*1024:raise ValueError(n)
    return hashlib.sha256(p.read_bytes()).hexdigest()
def spec(n):return {'source':n,'sha256':digest(n)}
def main():
    inputs={k:spec(n) for k,n in {
      'qa':V+'work/FINAL_TECHNICAL_QA_v9.json','config':V+'work/ROOT_FINAL_QA_CONFIG_v2.json',
      'extraction_receipt':P+'extract_attempt_1/COMPLETE.json','writer_receipt':P+'create_attempt_1/COMPLETE.json',
      'create_approval':P+'ROOT_CREATE_APPROVAL_v1.json','verify_approval':P+'ROOT_VERIFY_APPROVAL_v1.json',
      'addon_selection':P+'EVIDENCE_SELECTION_v1.json','addon_manifest':P+'extract_attempt_1/payload/MANIFEST.json',
      'standalone_reader_receipt':P+'READER_VERIFICATION_v1.json'}.items()}
    # Opaque ZIP is never opened or hashed in this proposal; exact approved receipt pin.
    inputs['archive']={'source':P+'create_attempt_1/v9_evidence.zip','sha256':'2d5bc9bfe0a614ee4fb53ec1bce6120eeda8304e5df6d2d85aedfc8501ac051b'}
    sources=['select_outer_v6.py','test_select_outer_v6.py','prepare_v6.py','package_v6.py','stream_common.py']
    required=[F+n for n in ['finalize_v9_v2.py','test_finalize_v9_v2.py','prepare_v9_final_config.py','test_prepare_v9_final_config.py']]+[V+n for n in ['assemble_submission.py','test_assemble_submission.py','build_documents.py','render_version.py','audit_layout.py']]
    prov=[P+n for n in ['PLAN.md','INVENTORY_PROPOSAL.json','plan_inventory.py','resolve_selection.py','resolve_snapshots.py','SOURCE_ALIAS_RESOLUTION.json','SELECTION_LINEAGE.json','CLOSURE_SCOPE.md','DEVELOPMENT_FAILURES.md','SOURCE_HANDOFF.md','OUTER_SELECTION_GENERATOR_HANDOFF.md','STREAMING_PROTOCOL.md','STREAM_SOURCE_REVIEW_HANDOFF.json','STREAM_SOURCE_V3_HANDOFF.md','write_evidence.py','verify_evidence.py','test_stream_evidence.py','PACKAGER_HANDOFF.md','PACKAGER_SOURCE_REVIEW.json','ROOT_PACKAGER_SOURCE_REVIEW.md','ROOT_STREAM_SOURCE_REVIEW.md','test_package_v6.py','test_prepare_v6.py','ROOT_CREATE_DECISION_v1.md','ROOT_INNER_INTEGRITY_RESULT.md','create_attempt_1/ATTEMPT.json']]
    prov += [P+'stream_v1_preserved/'+n for n in ['STREAMING_PROTOCOL.md','STREAM_SOURCE_REVIEW_HANDOFF.json','stream_common.py','write_evidence.py','verify_evidence.py','test_stream_evidence.py']]
    prov += [P+'stream_v2_preserved/'+n for n in ['STREAMING_PROTOCOL.md','stream_common.py','write_evidence.py','verify_evidence.py','test_stream_evidence.py']]
    prov += [P+'pre_external_v1/'+n for n in ['prepare_v6.py','test_prepare_v6.py']]
    prov += [F+n for n in ['STREAM_REVIEW_FINDINGS_1.md','STREAM_REVIEW_SUCCESSOR.md','test_stream_transport_review.py','test_stream_transport_successor.py','STREAM_SELECTION_QA.json','STREAM_SELECTION_QA_v2.json','STREAM_SELECTION_REVIEW.md','audit_stream_selection.py','ACTUAL_STREAM_QA.json','ACTUAL_STREAM_REVIEW.md','audit_actual_stream.py','V9_PACKAGE_GUIDE_REVIEW.md']]
    prov += [R+'package_v4_tools/'+n for n in ['package_v4.py','test_package_v4.py']]
    prov += [R+'model_proposal/editorial/v9_actual_final_review/'+n for n in ['QA.json','REVIEW.md','audit.py','NPZ_DESCRIPTION_ADDENDUM.md']]
    prov += [R+'model_proposal/editorial/saved_evidence_checker_review/'+n for n in ['REVIEW.md','ADVERSARIAL_FINDINGS.json','adversarial.py','FIRST_PROBE_PATH_FAILURE.md','SUCCESSOR_REVIEW.md','SUCCESSOR_COUNTEREXAMPLES.json','adversarial_successor.py']]
    prov += [V+'work/saved_evidence_checker_draft_v1/'+n for n in ['verify_saved_evidence.py','test_verify_saved_evidence.py']]
    prov += [F+'OUTER_SELECTOR_SOURCE_REVIEW.md',P+'propose_outer_approval.py']
    result={'schema':'v6-outer-selection-approval-1','phase':'PROPOSAL_ONLY_NOT_AUTHORIZED','source_pins':{P+n:digest(P+n) for n in sources},'inputs':inputs,'guide_pins':{n:digest(V+'work/package_documents/'+n) for n in ['README.md','NAVIGATION.md','PERMISSIONS.md','REPLAY_GUIDE.md','AUTHOR_CHECKLIST.md']},'helper_pins':{n:digest(V+'work/package_documents/'+n) for n in ['verify_saved_evidence.py','test_verify_saved_evidence.py']},'required_source_pins':{n:digest(n) for n in required},'provenance':[{**spec(n),'target':'quality/package_provenance/'+n} for n in sorted(prov)],'output':P+'OUTER_SELECTION_v1.json'}
    print(json.dumps(result,sort_keys=True,indent=2))
if __name__=='__main__':main()
