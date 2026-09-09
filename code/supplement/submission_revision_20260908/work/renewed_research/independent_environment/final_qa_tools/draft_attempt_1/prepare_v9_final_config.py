"""Finite V9 draft preparation only. Never invokes finalization or grants approval."""
from pathlib import Path
import argparse
import copy
import hashlib
import json

HERE = Path(__file__).resolve().parent
EDITION = 'submission_revision_20260908/renewed_manuscript_v9'
SCAFFOLD_SHA = '6e37520920b6052633db7ed3302c4bb6a0be04e1f83ae767e0dd4b8e6a66e3e4'
FRAGMENT_SHA = 'c9c14054db4972c9b5df34fb24f8bea6d030da60776a2d9265c9a9b7a4687d7b'
HELPER_SHA = '103c77f1e2a5da1be65a124b121c08d0b0fd089a0b5c2a9484590e4795a7278a'
ASSEMBLY_SHA = '2b5368e3cf0379117faf31dbaa05cf97aecc6d3726291f896d583719bd729375'
ASSEMBLY_CONFIG_SHA = '9c465fda5c7933381c8902bcd0e0cefb9952e4d23fbe08d9fe16a21ed3f808b9'
BUILDER_SHA = '7c8a02b0990e5c4e2f17c45b1518942d2e1d696aa5e41e94971f326bd4f7c973'
CONTENT = {'main': [17, 133, 4, 4], 'supplement': [43, 343, 44, 2], 'references': 23}
SELECTORS = {
 'main': dict(pages=33, stem='NeuralFoil_Measurement_Correction_Manuscript',
  source='afb27cf203ca9b00767aca6af41fe7d4cd40fa09cdb4deb83621a1b47d423df0',
  build='7229b0e3961ae9ca2bf84dd4ce4065b02947a047cb592e4849a6a56862719b87',
  layout='6d96121a33a09dff4b94febc30dd00e11c4edafb54298516fae67535ad17d127',
  page_map='3a78637574da9aa48fbd16cf12bcd4b40da23d66da856ffb70aac4bcc3cb5d2c',
  docx='2dd9e7d127d457cd74874c3ff14367be303a3cbb351e8dacd109f3c2f76f9112',
  pdf='440e8c09a326a40f0f6f865ebdc155c4c64fb7cca2f446aa2d76c9e6cf918d90'),
 'supplement': dict(pages=101, stem='NeuralFoil_Measurement_Correction_Supplement',
  source='1cb893cd04c3ad9400ee6a7b1e0fad99a80fafb6f410242318e17a65802143af')}
# Full literal supplement pins, separately readable to avoid hidden discovery.
SELECTORS['supplement'].update(
 build='e466c0d7dfe3b1fa16ce2d533368dc740297e994e25bc6d368c2795a60648aa7',
 layout='76d8ad27ce2f3d2d943717e7907cd2f31b408b5129764a9fba713a5c1a33ec5c',
 page_map='e1536ededa9e0602c738d658cd856fe10918d6c3164722a4a365b20ba7381859',
 docx='77493547cd44e38114a293926076d1f24a3bce0c691e82329e1a4aac8ef4f4d7',
 pdf='3da70f48fe206d2bc8b304afa1006b32d0e57b76c099307ce3e945848b456d56')

def require(ok, message):
    if not ok: raise ValueError(message)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def spec(path, sha): return {'path': str(path), 'sha256': sha}

def publish_draft(reading_path, output, reading, config):
    require(config['finalization_authorized'] is False, 'Cannot publish an authorized config')
    require(reading_path != output and not reading_path.exists() and not output.exists(), 'Clean outputs required')
    with reading_path.open('xb') as f: f.write(reading)
    with output.open('x') as f: json.dump(config, f, indent=2); f.write('\n')

def helper():
    path = HERE / 'finalize_v9.py'
    raw = path.read_bytes()
    require(digest(raw) == HELPER_SHA, 'Finalizer helper changed')
    # Execute precisely the authenticated buffer, not a second path import.
    import types
    module = types.ModuleType('v9_preparation_pinned_helper')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module

def validate_binding(b):
    require(set(b) == {'schema', 'preparation_authorized', 'finalization_authorized',
        'source_pins', 'visual', 'toc_labels', 'assembly_audit', 'assembly_review', 'assembly_binding_pointer', 'output_config'}, 'Strict binding fields')
    require(b['schema'] == 'v9-draft-preparation-binding-1', 'Binding schema')
    require(b['preparation_authorized'] is True and b['finalization_authorized'] is False, 'Preparation only authorization required')
    require(set(b['visual']) == set(CONTENT)-{'references'}, 'Both visual maps required')
    for kind, selected in SELECTORS.items():
        require(set(b['visual'][kind]) == {str(n) for n in range(1, selected['pages']+1)}, 'Incomplete visual coverage')
    for field in ('assembly_audit', 'assembly_review'):
        require(isinstance(b[field], dict) and b[field].get('path') and b[field].get('sha256'), 'Pending assembly review')
    require(b['assembly_audit'].get('role') == 'v9_assembly_audit' and b['assembly_audit'].get('assertions'), 'Audit role and explicit PASS assertion required')
    require(b['assembly_review'].get('role') == 'ancillary', 'Review must be explicit ancillary')
    require(isinstance(b['assembly_binding_pointer'], str) and b['assembly_binding_pointer'].startswith('/'), 'Explicit audit assembly hash pointer required')
    require(bool(b['toc_labels']), 'Root TOC selection required')
    require(Path(b['output_config']).parent.as_posix() == EDITION+'/work'
            and Path(b['output_config']).name.startswith('ROOT_FINAL_QA_CONFIG_DRAFT_')
            and Path(b['output_config']).suffix == '.json', 'Explicit new draft output path')

def assemble_draft(scaffold, fragment, binding, documents, assembly_entry, extra, reading_sha):
    """Pure composition; no approval inference and no scientific-map expansion."""
    validate_binding(binding)
    require(scaffold['finalization_authorized'] is False and scaffold['content_contract'] == CONTENT, 'Unexpected scaffold contract')
    require(scaffold['old_qa'] == fragment['legacy_old_qa_unmodified'], 'Legacy QA changed')
    required = fragment['legacy_evidence_unmodified'] + fragment['added_evidence']
    preserved = [e for e in scaffold['evidence'] if e.get('role') not in {'v9_assembly', 'v9_assembly_audit'}]
    require(preserved == required, 'Evidence history changed')
    c = copy.deepcopy(scaffold)
    for key in ('scaffold_status', 'unresolved', 'history_pins_for_root_ancillary_selection'):
        c.pop(key, None)
    c['documents'] = copy.deepcopy(documents)
    c['documents']['supplement']['reading_source'] = spec(EDITION+'/supplement.reading.md', reading_sha)
    history = [dict(path=e['path'], sha256=e['sha256'], role='ancillary',
                    historical_role=e.get('role', 'historical_failed_review_not_pass')) for e in fragment['history_pins']]
    c['evidence'] = copy.deepcopy(required + [assembly_entry, binding['assembly_audit'], binding['assembly_review']] + history + extra)
    c['finalization_authorized'] = False
    c['preparation_status'] = 'PREPARED_DRAFT_NOT_AUTHORIZED_FOR_FINALIZATION'
    c['counts_scope'] = 'Explicit root-selected v2 build contract; finalizer must independently verify native counts'
    return c

def prepare(root, binding_path, binding_sha):
    h = helper(); pins = h.Pins(root)
    binding_file = pins.pin(spec(binding_path, binding_sha))
    b = json.loads(binding_file.read_text()); validate_binding(b)
    expected_sources = {str(HERE/'prepare_v9_final_config.py'), str(HERE/'test_prepare_v9_final_config.py'), str(HERE/'finalize_v9.py'), str(HERE/'test_finalize_v9.py')}
    require(set(b['source_pins']) == expected_sources, 'Exact helper/source/test inventory required')
    for path, sha in b['source_pins'].items(): pins.pin(spec(path, sha))
    scaffold_file = pins.pin(spec(HERE/'V9_FINALIZER_SCAFFOLD_UNAUTHORIZED.json', SCAFFOLD_SHA))
    fragment_file = pins.pin(spec(HERE/'V9_EVIDENCE_FRAGMENT_DRAFT_v4.json', FRAGMENT_SHA))
    scaffold = json.loads(scaffold_file.read_text()); fragment = json.loads(fragment_file.read_text())
    edition = pins.path(EDITION)
    reading_path = edition/'supplement.reading.md'; output = pins.path(b['output_config'])
    require(not reading_path.exists() and not output.exists(), 'Clean outputs required')
    assembly_file = pins.pin(spec(edition/'work/ASSEMBLY.json', ASSEMBLY_SHA))
    pins.pin(spec(edition/'work/assembly_versions/v2/CONFIG.json', ASSEMBLY_CONFIG_SHA))
    assembly = json.loads(assembly_file.read_text())
    require(assembly['version'] == 'v2', 'Assembly version')
    audit = json.loads(pins.pin(b['assembly_audit']).read_text())
    for assertion in b['assembly_audit']['assertions']:
        require(h.pointer(audit, assertion['pointer']) == assertion['equals'], 'Audit assertion failed')
    # The selected audit must explicitly bind this assembly, not just say PASS.
    require(h.pointer(audit, b['assembly_binding_pointer']) == ASSEMBLY_SHA, 'Audit does not bind selected assembly')
    pins.pin(b['assembly_review'])
    documents = {}
    for kind, selected in SELECTORS.items():
        base = edition/'work'/('render_'+kind)/'v2'
        d = dict(version='v2', pages=selected['pages'], visual=b['visual'][kind])
        paths = dict(source=edition/(kind+'.complete.md'), builder=base/'build_documents.py',
            build=base/'BUILD.json', layout=base/'LAYOUT_AUDIT.json', page_map=base/'PAGE_MAP.json',
            docx=base/(selected['stem']+'.docx'), pdf=base/(selected['stem']+'.pdf'))
        for key, path in paths.items(): d[key] = spec(path, BUILDER_SHA if key == 'builder' else selected[key]); pins.pin(d[key])
        build = json.loads(paths['build'].read_text()); layout = json.loads(paths['layout'].read_text())
        require([build[k] for k in ('equations','all_math_objects','tables','figures')] == CONTENT[kind], 'Build content counts')
        require(build['source_sha256'] == selected['source'] and build['builder_sha256'] == BUILDER_SHA and build['docx_sha256'] == selected['docx'], 'Build chain')
        require(layout['status'] == 'PASS_PROGRAMMATIC' and not layout['violations'] and layout['pages'] == selected['pages'] and layout['pdf_sha256'] == selected['pdf'], 'Layout selection')
        ledger = {str(row['page']): row['png_sha256'] for row in layout['ledger']}
        require(set(ledger) == set(d['visual']), 'Layout page set')
        for number, entry in d['visual'].items():
            current = pins.pin(spec(base/('page-'+number+'.png'), ledger[number]))
            h.visual_page(pins, current, entry)
        d['deliverable_docx'] = str(edition/'deliverables'/(selected['stem']+'.docx'))
        pins.pin(spec(d['deliverable_docx'], selected['docx']))
        d['deliverable_pdf'] = str(edition/'deliverables'/(selected['stem']+'.pdf'))
        documents[kind] = d
    documents['supplement']['toc_labels'] = b['toc_labels']
    source = pins.path(documents['supplement']['source']['path']).read_bytes()
    pages = json.loads(pins.path(documents['supplement']['page_map']['path']).read_text())
    reading = h.reading_source_bytes('supplement', source, b['toc_labels'], pages)
    assembly_entry = dict(path=str(assembly_file), sha256=ASSEMBLY_SHA, role='v9_assembly',
        assertions=[{'pointer':'/status','equals':'ASSEMBLED_NOT_RENDERED_OR_VISUALLY_VERIFIED'}],
        maps=[{'pointer':'/'+p,'base':str(edition) if p=='outputs' else str(root)} for p in ('inputs','outputs','asset_sha256')],
        scalar_pins=[{'pointer':'/assembler_sha256','path':str(edition/'assemble_submission.py')},
                     {'pointer':'/config/sha256','path':str(edition/'work/assembly_versions/v2/CONFIG.json')}])
    extra = [dict(path=path, sha256=sha, role='ancillary') for path, sha in pins.files.items()]
    c = assemble_draft(scaffold, fragment, b, documents, assembly_entry, extra, digest(reading))
    pins.reread()
    # Exclusive writes, not a transaction. Preserve any first file on interruption;
    # manual reviewed successor paths are required, never automatic overwrite/retry.
    publish_draft(reading_path, output, reading, c)
    return {'status': c['preparation_status'], 'reading_sha256':digest(reading), 'config_sha256':digest(output.read_bytes())}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--binding', required=True); ap.add_argument('--binding-sha256', required=True)
    a = ap.parse_args(); print(json.dumps(prepare(Path(a.root), a.binding, a.binding_sha256), indent=2))
