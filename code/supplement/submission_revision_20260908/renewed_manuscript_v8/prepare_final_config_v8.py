"""Prepare an unauthorized, explicit V8 technical-QA config; no finalizer execution.

This assembles existing metadata only. Root must review a separately authenticated
current assembly-delta witness before authorizing a successor config. Historical
evidence stays pinned to its historical paths; it is not relabeled as current QA.
"""
import hashlib
import json
from pathlib import Path

EDITION = Path(__file__).resolve().parent
PROJECT = EDITION.parents[1]
BASE = EDITION.parent
RESEARCH = BASE / 'work/renewed_research'

def pin(path, expected=None):
    path = Path(path).absolute()
    if not path.is_relative_to(PROJECT) or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe metadata path')
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and h != expected:
        raise ValueError('Changed pinned input: ' + str(path))
    return {'path': str(path.relative_to(PROJECT)), 'sha256': h}

def read(path, expected):
    record = pin(path, expected)
    return json.loads((PROJECT / record['path']).read_text())

def evidence(role, path, expected=None, assertions=None, maps=None):
    r = {'role': role, **pin(path, expected), 'assertions': assertions or []}
    if maps:
        r['maps'] = maps
    return r

def main():
    oldpath = BASE / 'renewed_manuscript_v7/work/ROOT_FINAL_QA_CONFIG_v3.json'
    old = read(oldpath, 'cbd25ed36e0f1527e96d811bd990b79ffb46ed0f23515d53c704f78f97af654f')
    draftpath = EDITION / 'work/V8_NEW_EVIDENCE_DRAFT.json'
    draft = read(draftpath, '931662ffa650afec0e8f25f17feef59d13308f348716dd73ef3a1ecad5248d5b')
    visualpath = EDITION / 'work/VISUAL_BINDINGS_FINAL.json'
    visual = read(visualpath, '6d0c83efb87db3878bb493420b08f7678398493bf31a64483bdb2052542652aa')
    assert draft['finalization_authorized'] is False
    assert len(draft['evidence']) == 13 and len(draft['ancillary']) == 45
    assert visual['direct_pages'] == 89 and visual['inherited_pages'] == 21
    cfg = {k:v for k,v in old.items() if k not in ('documents','evidence','root_authorization')}
    cfg.update(schema='v8-final-qa-1', edition=str(EDITION.relative_to(PROJECT)),
               finalization_authorized=False,
               content_contract={'main':[17,133,4,4],'supplement':[39,298,35,2],'references':21},
               root_authorization={'scope':'DRAFT ONLY: requires root-read independent current assembly audit and explicit final authorization.'})
    cfg['documents'] = {}
    for kind, version, pages, name, sourcehash, pdfhash in (
        ('main','v2',30,'Manuscript','768ffc2a37b7ecae4e644fa00a04a367c2e86868f1ff2981a6b700f843a8357e','f3a0775cf53a9213df69c8e5ca2722a990a96801bfebe4d02bdc732f026a2cf6'),
        ('supplement','v3',80,'Supplement','cd1fd7942bd7dbf1881a6012d8c90de5726315f45d0c97b7651e0bf709c81157','d8e51b01a6131a7c111f558b39617cf1018fecbe0aac635e084d755d46ffc5d4')):
        render = EDITION / ('work/render_'+kind) / version
        stem = 'NeuralFoil_Measurement_Correction_'+name
        d = {'version':version,'pages':pages,'source':pin(EDITION/(kind+'.complete.md'),sourcehash)}
        for key, file in [('builder','build_documents.py'),('build','BUILD.json'),('layout','LAYOUT_AUDIT.json'),('page_map','PAGE_MAP.json'),('docx',stem+'.docx')]:
            d[key] = pin(render/file)
        d['pdf'] = pin(render/(stem+'.pdf'),pdfhash)
        for suffix in ('pdf','docx'):
            d['deliverable_'+suffix] = str((EDITION/'deliverables'/(stem+'.'+suffix)).relative_to(PROJECT))
        d['visual'] = visual['documents'][kind]
        if kind == 'supplement':
            d['toc_labels'] = old['documents'][kind]['toc_labels']
            d['reading_source'] = pin(EDITION/'supplement.reading.md','3b2dfdc9da1c2caf1c8f3af0146d41df6631a6025a249eae646ba72717ad863d')
        cfg['documents'][kind] = d
    cfg['evidence'] = old['evidence']
    # Explicitly retain old assembly audits as historical; add the current assembly.
    for item in cfg['evidence']:
        if item['role'] in ('assembly','assembly_audit','assembly_delta_audit'):
            item['historical_role'] = item['role']
            item['role'] = 'ancillary'
    assembly = evidence('assembly', EDITION/'work/ASSEMBLY.json',
        '8d3517f09f2dc1044baf388d9e2a96fe352873aebbbdca8e0443d008da29c373',
        [{'pointer':'/status','equals':'PASS'},
         {'pointer':'/main_sha256','equals':cfg['documents']['main']['source']['sha256']},
         {'pointer':'/supplement_sha256','equals':cfg['documents']['supplement']['source']['sha256']},
         {'pointer':'/references','equals':21}], [{'pointer':'/source_sha256','base':'.'}])
    assembly['scalar_pins'] = [{'pointer':'/code_sha256','path':str((EDITION/'assemble_submission.py').relative_to(PROJECT))}]
    cfg['evidence'].append(assembly)
    # These copied manifests have unchanged recorded source paths, but their
    # relative output maps must explicitly refer to the current edition copies.
    for role in ('legacy_displays','method_diagram','risk_displays','sensitivity_displays'):
        ancestral = next(x for x in old['evidence'] if x['role'] == role)
        cur = json.loads(json.dumps(ancestral))
        cur['path'] = cur['path'].replace('/renewed_manuscript_v7/', '/renewed_manuscript_v8/')
        pin(PROJECT/cur['path'],cur['sha256'])
        for m in cur.get('maps',[]):
            if m['base'].endswith('/renewed_manuscript_v7'):
                m['base'] = str(EDITION.relative_to(PROJECT))
        cfg['evidence'].append(cur)
    cfg['evidence'].extend(draft['evidence'])
    for item in draft['ancillary']:
        assertions = [{'pointer':'/status','equals':item['observed_status']}] if 'observed_status' in item else []
        cfg['evidence'].append(evidence('ancillary',PROJECT/item['path'],item['sha256'],assertions))
    for p in (oldpath,draftpath,visualpath,EDITION/'work/READING_COPY.json',EDITION/'build_visual_ledger_v8.py',EDITION/'build_reading_copy_v8.py',Path(__file__)):
        cfg['evidence'].append(evidence('ancillary',p))
    cfg['pending_root_actions'] = ['Add separately reviewed current assembly_audit and editorial delta witness',
        'Read independent config review before producing explicitly authorized successor',
        'Run frozen finalizer once; this script does not run it']
    target = EDITION / 'work/ROOT_FINAL_QA_CONFIG_DRAFT_v1.json'
    raw = (json.dumps(cfg,indent=2)+'\n').encode()
    with target.open('xb') as f:
        f.write(raw)
    print(json.dumps({'status':'DRAFT_ONLY','path':str(target),'sha256':hashlib.sha256(raw).hexdigest(),
                      'evidence_records':len(cfg['evidence']),'finalization_authorized':False}))

if __name__ == '__main__':
    main()
