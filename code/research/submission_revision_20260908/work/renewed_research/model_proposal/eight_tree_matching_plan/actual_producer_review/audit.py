"""Saved eight-producer metadata audit. No model imports or proof evaluation.

Only the new JSONL is parsed, one record at a time, for declared inventory.
Old certificates and NPZs are hashed as opaque bytes, never parsed.
"""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent
ROOT = PLAN.parents[1]
REG = '63ebf6b33a512fd33e13156fb086bef867000d773715f7828fd16a92a452facf'
APP = 'b8a05edbba1e11d5d5b365892c4e3bcb3a07d462940fb3ba9993d84f121f000b'
CERT = '718257949921d96d966813e881a5073551d6c4712ae8cdbc406f3bea36105df5'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(65536), b''):
            h.update(part)
    return h.hexdigest()


def inventory(path):
    counts = dict(stages=0, blocks=0, paths=0, path_edges=0,
                  pair_classifications=0, feasible_pairs=0)
    statuses = Counter()
    sizes = []
    with path.open('rb') as f:
        for index, raw in enumerate(f):
            assert raw.endswith(b'\n') and len(raw) <= 2**20
            sizes.append(len(raw))
            r = json.loads(raw)
            assert json.dumps(r, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()+b'\n' == raw
            if index == 0:
                header = r
                assert r['kind'] == 'header' and r['schema'] == 'EIGHT_TREE_MATCHING_JSONL_V1'
                assert r['stages'] == 400 and r['blocks'] == 50 and r['domain'] == 'FINITE_X62_V1'
            elif index <= 400:
                assert r['kind'] == 'paths' and r['stage'] == index-1
                leaves = r['leaves']
                assert len(leaves) <= 15 and len({v['leaf'] for v in leaves}) == len(leaves)
                assert [v['leaf'] for v in leaves] == sorted(v['leaf'] for v in leaves)
                assert all(len(v['edges']) <= 14 for v in leaves)
                counts['stages'] += 1
                counts['paths'] += len(leaves)
                counts['path_edges'] += sum(len(v['edges']) for v in leaves)
            elif index <= 450:
                j = index-401
                assert r['kind'] == 'block' and r['block'] == j
                assert r['stages'] == list(range(8*j,8*j+8)) and r['old4_stage'] == 8*(j+1)
                assert len(r['pairs']) == 28 and len(r['matchings']) == 105 and len(r['error_steps']) == 8
                assert [p['stages'] for p in r['pairs']] == [list(x) for x in itertools.combinations(range(8*j,8*j+8),2)]
                for p in r['pairs']:
                    values = bytes.fromhex(p['status_hex'])
                    assert len(values) == p['shape'][0]*p['shape'][1]
                    assert set(values) <= {0,1,2} and values.count(2) == p['feasible']
                    statuses.update(values)
                    counts['pair_classifications'] += len(values)
                    counts['feasible_pairs'] += p['feasible']
                assert len({tuple(m['pair_indices']) for m in r['matchings']}) == 105
                assert all(len(m['pair_indices']) == 4 for m in r['matchings'])
                counts['blocks'] += 1
            else:
                assert index == 451 and r['kind'] == 'footer'
                footer = r
    assert len(sizes) == 452 and footer['counts'] == counts
    return dict(header=header, footer=footer, counts=counts, lines=len(sizes),
                stream_bytes=sum(sizes), maximum_line_bytes=max(sizes),
                status_counts={str(k):statuses[k] for k in (0,1,2)})


def main():
    pins, parses = {}, []
    def pin(path, expected=None):
        path.relative_to(ROOT)
        assert not any(p.is_symlink() for p in (path,*path.parents))
        h = digest(path)
        if expected is not None:
            assert h == expected, str(path)
        pins[str(path.relative_to(ROOT))] = h
        return h
    def read(path, expected=None):
        h = pin(path,expected)
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == h
        parses.append(str(path.relative_to(ROOT)))
        return json.loads(raw)
    attempt = PLAN/'producer_attempt_1'
    reg = read(PLAN/'PRODUCER_REGISTRY.json',REG)
    approval = read(PLAN/'ROOT_PRODUCER_APPROVAL.json',APP)
    complete = read(attempt/'COMPLETE.json')
    review = read(PLAN/'ROOT_PRODUCER_SOURCE_REVIEW.json',approval['source_review_sha256'])
    gate = read(PLAN/'COLD_GATE_PASS.json',approval['cold_gate_sha256'])
    assert review['status'] == 'PASS_SOURCE_REVIEW'
    assert complete['status'] == 'COMPLETE' and complete['phase'] == 'producer'
    assert complete['registry_sha256'] == REG and complete['approval_sha256'] == APP
    assert approval['registry_sha256'] == REG and approval['output'] == attempt.name
    assert approval['actual_execution_authorized'] is True
    assert complete['source_pins'] == reg['sources'] and complete['helper_pins'] == reg['helpers']
    assert gate['independent_result']['counts']['pair_classifications'] == 315000
    for name,h in reg['sources'].items(): pin(PLAN/name,h)
    for entry in reg['helpers'].values(): pin(ROOT/entry['path'],entry['sha256'])
    refs = {}
    for role,entry in reg['inputs'].items():
        if role == 'model': pin(ROOT/entry['path'],entry['sha256'])
        else: refs[role] = read(ROOT/entry['path'],entry['sha256'])
    cc,cr = refs['capsule_complete'],refs['capsule_registry']
    assert cc['status'] == 'COMPLETE' and cc['outputs']['CAPSULE.json'] == reg['inputs']['capsule']['sha256']
    assert cc['approval_sha256'] == reg['inputs']['capsule_approval']['sha256']
    assert cc['registry_sha256'] == reg['inputs']['capsule_registry']['sha256']
    for entry in cr['inputs'].values(): pin(ROOT/entry['path'],entry['sha256'])
    for name,h in cc['outputs'].items(): pin((ROOT/reg['inputs']['capsule_complete']['path']).parent/name,h)
    for name,h in complete['outputs'].items(): pin(attempt/name,h)
    assert set(p.name for p in attempt.iterdir()) == set(complete['outputs'])|{'COMPLETE.json'}
    assert complete['outputs']['certificate.jsonl'] == CERT
    access = read(attempt/'ACCESS.json',complete['outputs']['ACCESS.json'])
    for event in access:
        if 'path' in event and 'sha256' in event: pin(Path(event['path']),event['sha256'])
    members = [e for e in access if e['operation'] == 'NPZ_materialization']
    expected_members = {'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'}
    assert len(members) == 7 and {e['member'] for e in members} == expected_members
    assert all(e['model_sha256'] == reg['inputs']['model']['sha256'] for e in members)
    inv = inventory(attempt/'certificate.jsonl')
    assert inv['header']['model_sha256'] == reg['inputs']['model']['sha256']
    assert inv['header']['old4_certificate_sha256'] == refs['capsule']['certificate_sha256']
    assert inv['header']['old4_replay_complete_sha256'] == refs['capsule']['replay_complete_sha256']
    summary = complete['summary']
    assert all(inv['footer'][key] == summary[key] for key in ('counts','original_four','final'))
    assert summary['original_four'] == refs['capsule']['final']
    assert summary['fits'] == summary['features_targets_calibration_loaded'] == 0
    assert summary['model_materializations'] == 1 and summary['old4_proof_inherited'] is True
    assert summary['accounting']['status'] == 'CONDITIONAL_NO_PRODUCTION_ADAPTER_REVIEW'
    assert summary['accounting']['estimate'] <= 128*2**20
    sizes = {p.name:p.stat().st_size for p in attempt.iterdir()}
    assert sum(sizes.values()) <= 64*2**20 and complete['elapsed_seconds'] <= 900
    assert complete['limits'] == dict(output_cap=64*2**20,owned_cap=128*2**20,seconds=900,workers=1)
    # Extract literal role identities from authenticated source AST without imports.
    replay = PLAN/'replay_plan/replay.py'
    pin(replay,'a20a7e92909a5d35a8f85d3cad22305f4c0a9cd4dc15942bb9ed5f2ffb24da18')
    tree = ast.parse(replay.read_text())
    helpers = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HELPERS' for t in n.targets))
    inputs = {role:entry for role,entry in cr['inputs'].items()}
    inputs['model'] = reg['inputs']['model']
    for role,name in [('certificate','producer_attempt_1/certificate.jsonl'),('producer_complete','producer_attempt_1/COMPLETE.json'),('producer_approval','ROOT_PRODUCER_APPROVAL.json'),('producer_registry','PRODUCER_REGISTRY.json')]:
        p = PLAN/name
        inputs[role] = dict(path=str(p.relative_to(ROOT)),sha256=pin(p))
    assert len(inputs) == 13
    proposal = dict(schema='EIGHT_REPLAY_SOURCE_V1',sources={'replay.py':pin(replay)},
                    helpers={k:dict(path=v[0],sha256=v[1]) for k,v in helpers.items()},inputs=inputs)
    for entry in proposal['helpers'].values(): pin(ROOT/entry['path'],entry['sha256'])
    # End reauthentication, not scientific re-execution.
    for p,h in pins.items(): assert digest(ROOT/p) == h
    qa = dict(status='PASS_SAVED_METADATA_AND_STREAM_INVENTORY_ONLY',utc=datetime.now(timezone.utc).isoformat(),
              audit_source_sha256=digest(Path(__file__)),pins=pins,unique_pins=len(pins),metadata_parses=parses,
              complete=complete,stream_inventory=inv,output_sizes=sizes,actual_output_bytes=sum(sizes.values()),
              producer_access_records=len(access),producer_materialized_members=members,
              independent_audit_model_materializations=0,independent_proof_replays=0,
              limitation='Exact bounds are transcribed, not independently re-proved. Conditional accounting status retained verbatim; owned-memory estimate is not measured RSS. Independent actual mathematical replay still required.')
    for name,obj in [('QA.json',qa),('REPLAY_REGISTRY_PROPOSAL.json',proposal)]:
        raw = (json.dumps(obj,indent=2,sort_keys=True)+'\n').encode()
        with (HERE/name).open('xb') as f: f.write(raw)
    print(json.dumps(dict(status=qa['status'],unique_pins=len(pins),counts=inv['counts'],outputs=sizes,qa_sha256=digest(HERE/'QA.json'),proposal_sha256=digest(HERE/'REPLAY_REGISTRY_PROPOSAL.json'))))


if __name__ == '__main__': main()
