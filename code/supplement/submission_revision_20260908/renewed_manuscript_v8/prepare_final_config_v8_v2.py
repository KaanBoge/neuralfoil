"""Add the root-read current assembly bridge to the still-unauthorized V8 config."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('metadata_preparer', HERE/'prepare_final_config_v8.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)

def main():
    p = HELPER
    priorpath = HERE/'work/ROOT_FINAL_QA_CONFIG_DRAFT_v1.json'
    cfg = p.read(priorpath,'05d32d421712db9b6f114c6800b27eee72bbc2a0ee11fada9d5c5413ce6cbc8e')
    reviewdir = p.RESEARCH/'model_proposal/editorial/v8_reauthentication'
    rolespath = reviewdir/'FINALIZER_ROLE_DRAFT.json'
    roles = p.read(rolespath,'5a729620ad59fc39039df5cd45b2407d3ee3dd23b290aed133120b816f2d73e5')
    assert not cfg['finalization_authorized'] and not roles['finalization_authorized']
    cfg['evidence'] = [e for e in cfg['evidence'] if e['role'] != 'assembly']
    cfg['evidence'].extend(roles['evidence'])
    for path in (priorpath,rolespath,reviewdir/'REPORT.md',reviewdir/'FIRST_ATTEMPT.md',Path(__file__)):
        cfg['evidence'].append(p.evidence('ancillary',path))
    finaldir = p.RESEARCH/'independent_environment/final_qa_tools'
    for name, expected in (
        ('finalize_v8.py','013bf9d87a7a16d72c75b3e68f6d089997c95cf5abe715541fe23af361ed7570'),
        ('test_finalize_v8.py','d5bb9e88cd7dd4e773a334e2fa7f0b397bae9d5c4669f70b37c4e2ce62702671'),
        ('V8_FINALIZER.diff',None),('V8_FINALIZER_CONTRACT.md',None),('V8_SOURCE_QA.json',None)):
        cfg['evidence'].append(p.evidence('ancillary',finaldir/name,expected))
    cfg['pending_root_actions'] = ['Read independent complete config/evidence/source binding review',
        'Produce a separately pinned explicit authorization successor; this draft remains false',
        'Run frozen finalizer once and publish identical PDFs only after all gates pass']
    cfg['root_authorization']['basis'] = (
        'Root read current assembly reauthentication report and actual machine assertions; '
        'current and historical sources have distinct exact maps. All 110 visual bindings '
        'and exact reading-source substitution are unchanged. Independent config review remains.')
    # Metadata-only assertion/map pin pass; no finalizer or document/scientific execution.
    modspec = importlib.util.spec_from_file_location('v8_gate',finaldir/'finalize_v8.py')
    gate = importlib.util.module_from_spec(modspec)
    modspec.loader.exec_module(gate)
    pins = gate.Pins(p.PROJECT)
    for e in cfg['evidence']:
        path = pins.pin(e)
        obj = json.loads(path.read_text()) if any(e.get(k) for k in ('assertions','maps','record_lists','scalar_pins')) else None
        gate.extra_evidence(pins,e,obj)
        for a in e.get('assertions',[]):
            assert gate.pointer(obj,a['pointer']) == a['equals'], (e['role'],a)
        for m in e.get('maps',[]):
            for rel,h in gate.pointer(obj,m['pointer']).items():
                path = Path(rel) if Path(rel).is_absolute() else pins.path(m['base'])/rel
                pins.pin({'path':str(path),'sha256':h})
    pins.reread()
    target = HERE/'work/ROOT_FINAL_QA_CONFIG_DRAFT_v2.json'
    raw = (json.dumps(cfg,indent=2)+'\n').encode()
    with target.open('xb') as f:
        f.write(raw)
    print(json.dumps({'status':'DRAFT_METADATA_BOUND_NOT_FINALIZED','path':str(target),
        'sha256':hashlib.sha256(raw).hexdigest(),'evidence_records':len(cfg['evidence']),
        'unique_metadata_and_mapped_files':len(pins.files),'finalization_authorized':False}))

if __name__ == '__main__': main()
