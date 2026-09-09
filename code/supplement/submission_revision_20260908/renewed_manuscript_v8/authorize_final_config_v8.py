"""Explicit root authorization after the complete independent V8 config review.

Only metadata is written. This does not execute the finalizer or claim its PASS.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RESEARCH = HERE.parent/'work/renewed_research'

def checked(path, expected):
    path = Path(path).absolute()
    assert path.is_relative_to(PROJECT) and not any(p.is_symlink() for p in (path,*path.parents))
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, str(path)
    return raw

def pin(path, h=None):
    path = Path(path).absolute()
    if h is None:
        h = hashlib.sha256(path.read_bytes()).hexdigest()
    checked(path,h)
    return {'path':str(path.relative_to(PROJECT)),'sha256':h,'role':'ancillary','assertions':[]}

def main():
    draftpath = HERE/'work/ROOT_FINAL_QA_CONFIG_DRAFT_v2.json'
    draftsha = 'c7438e8ef28d53c6e324bf632f6a56cc882671a7b2d1a6a58a07a8662944f7cd'
    cfg = json.loads(checked(draftpath,draftsha))
    rdir = RESEARCH/'model_proposal/editorial/v8_config_review'
    rsha = 'a4f12afb41d45c2aa2aad8264d3b57b09e2bad17c2db576851c57ccd6bc8f1f9'
    reportsha = '8ecd74811df373de5b8d7197a022c078dd1be342057cdb3848e7db1e47fba531'
    review = json.loads(checked(rdir/'REVIEW.json',rsha))
    report = checked(rdir/'REPORT.md',reportsha).decode()
    assert draftsha in report and 'PASS' in report
    assert review['status'] == 'PASS_CONFIG_METADATA_AND_BINDING_REVIEW_NOT_FINALIZATION'
    assert review['config_sha256'] == draftsha and review['evidence_records'] == 114
    assert review['finalization_authorized'] is False and review['finalizer_executed'] is False
    assert cfg['finalization_authorized'] is False
    helper = RESEARCH/'independent_environment/final_qa_tools/finalize_v8.py'
    checked(helper,'013bf9d87a7a16d72c75b3e68f6d089997c95cf5abe715541fe23af361ed7570')
    cfg['finalization_authorized'] = True
    cfg.pop('pending_root_actions')
    cfg['root_authorization'] = {
        'at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'One internal V8 technical finalization and absent-or-identical PDF copy only; no scientific execution, author approval, rights clearance, public release or submission.',
        'basis':'Root read the full finalizer narrow diff, inherited source and new tests, passed all48 synthetic tests, directly reviewed89 pages and verified21 inherited full-PNG pages, read the current assembly and independent full config reports, and inspected actual assertions/maps. Scientific/evidence/render/visual choices are unchanged from the independently reviewed draft.',
        'reviewed_draft_sha256':draftsha,'independent_review_sha256':rsha,
        'independent_review_report_sha256':reportsha}
    cfg['evidence'].extend([pin(draftpath,draftsha),pin(rdir/'REPORT.md',reportsha),
        pin(rdir/'audit.py',review['review_source_sha256']),pin(Path(__file__))])
    e = pin(rdir/'REVIEW.json',rsha)
    e['assertions'] = [{'pointer':'/status','equals':review['status']},
        {'pointer':'/config_sha256','equals':draftsha},
        {'pointer':'/finalizer_executed','equals':False},
        {'pointer':'/evidence_records','equals':114}]
    cfg['evidence'].append(e)
    raw = (json.dumps(cfg,indent=2)+'\n').encode()
    target = HERE/'work/ROOT_FINAL_QA_CONFIG_FINAL_v1.json'
    with target.open('xb') as f:
        f.write(raw)
    print(json.dumps({'status':'AUTHORIZED_TECHNICAL_FINALIZATION_ONLY','path':str(target),
        'sha256':hashlib.sha256(raw).hexdigest(),'evidence_records':len(cfg['evidence'])}))

if __name__ == '__main__':main()
