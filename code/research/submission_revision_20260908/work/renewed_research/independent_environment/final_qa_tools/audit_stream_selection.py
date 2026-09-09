"""Finite metadata/source-only selection review; never read scientific payloads."""
import hashlib, json, tarfile
from pathlib import Path

PROJECT = Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
BASE = PROJECT / 'submission_revision_20260908/work/renewed_research/uncertainty_review/package_v6_plan'
READS = {}

def read(path, expected=None):
    b = path.read_bytes()
    h = hashlib.sha256(b).hexdigest()
    if expected is not None:
        assert h == expected, str(path)
    READS[str(path)] = h
    return b

def main():
    expected = {
        'INVENTORY_PROPOSAL.json':'79fb68943cc5f23f9219f9dff06efe9bdc8ef1b435a879eadb3b07c0e723ec68',
        'EVIDENCE_SELECTION_v1.json':'5b92757d129cba7198c987d1c6ed090abc98a4c35c1a73448568af2dcc7283c5',
        'SELECTION_LINEAGE.json':'d4e84c7ff7d1dd8c7d122451fd20e7bf7c73cc4c2a3f7a60e08d80bb3ff44ae9',
        'SOURCE_ALIAS_RESOLUTION.json':'69f2a9f97ea15707712efda9adad225da938c9e26984ad148efb549c73256b87',
        'CLOSURE_SCOPE.md':'4ac2918a263e8142f2263e21ed265f157ed434cb91905c7950a65bf2ed4341b4',
    }
    docs = {n:read(BASE/n,h) for n,h in expected.items()}
    proposal, selection, lineage, aliases = [json.loads(docs[n]) for n in list(expected)[:4]]
    rows = {r['source']:r for r in selection['files']}
    assert len(rows) == len(selection['files']) == 1644
    assert sum(r['bytes'] for r in rows.values()) == 934080471
    assert selection['schema'] == 'v9-evidence-selection-1' and selection['unresolved'] == []
    assert selection['claim'] == 'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE'
    assert len({r['target'].casefold() for r in rows.values()}) == len(rows)
    for r in rows.values():
        assert r['target'] == 'project/'+r['source']
        assert not Path(r['source']).is_absolute() and '..' not in Path(r['source']).parts
        p=PROJECT/r['source']
        assert p.is_file() and not any(x.is_symlink() for x in (p,*p.parents))
        assert p.stat().st_size == r['bytes']
    original = {r['source']:r for r in proposal['addon_files']}
    alias_paths = {r['original_path'] for r in aliases['bindings']}
    preserved = 0
    for n,r in original.items():
        if n in alias_paths: continue
        assert (rows[n]['sha256'],rows[n]['bytes']) == (r['sha256'],r['bytes'])
        preserved += 1
    unresolved = proposal['unresolved_schema_records']
    external = [r for r in unresolved if set(r)=={'external_runtime_not_packaged','sha256'}]
    conflicts = [r for r in unresolved if set(r)=={'historical_source_needs_snapshot','sha256','other_sha256'}]
    assert len(external)==360 and len(conflicts)==20 and len(unresolved)==380
    assert lineage['external_runtime_exclusions']==external
    assert lineage['source_substitutions']==aliases['bindings']
    wanted={(r['historical_source_needs_snapshot'],r['sha256']) for r in conflicts}
    wanted.update((n,original[n]['sha256']) for n in alias_paths)
    actual={(r['original_path'],r['expected_sha256']) for r in aliases['bindings']}
    assert wanted==actual and len(actual)==15
    source_members=[]
    for n,h in aliases['source_archives'].items():
        assert Path(n).name in {'SOURCE_V1_PRESERVED.tar','SOURCE_V2_PRESERVED.tar'}
        read(PROJECT/n,h)
        assert rows[n]['sha256']==h
        with tarfile.open(PROJECT/n,'r:') as archive:
            for binding in aliases['bindings']:
                r=binding['resolution']
                if r['source']!=n: continue
                m=archive.getmember(r['member'])
                assert m.isfile() and m.size==r['bytes'] and m.size<=1024*1024
                b=archive.extractfile(m).read()
                assert hashlib.sha256(b).hexdigest()==r['sha256']==binding['expected_sha256']
                source_members.append({'archive':n,'member':m.name,'sha256':r['sha256']})
    for binding in aliases['bindings']:
        r=binding['resolution']
        if r['kind']=='current_source_file':
            read(PROJECT/r['source'],r['sha256'])
            assert rows[r['source']]['sha256']==binding['expected_sha256']==r['sha256']
        else: assert r['kind']=='preserved_source_tar_member'
    metadata={}
    for n,h in proposal['metadata_json_parsed'].items():
        metadata[n]=json.loads(read(PROJECT/n,h))
    child=[]; inherited=[]; output_links=0
    for n,d in metadata.items():
        if Path(n).name!='COMPLETE.json': continue
        for out,h in d.get('outputs',{}).items():
            k=str(Path(n).parent/out)
            assert k in rows and rows[k]['sha256']==h, k
            output_links += 1
        if '/certificates_' in n:
            contexts=d.get('contexts',d.get('summary',{}).get('contexts',{}))
            if contexts:
                assert len(contexts)==16
                for context,r in contexts.items():
                    if context=='final':continue
                    k=str(Path(n).parent/context/'COMPLETE.json')
                    assert rows[k]['sha256']==r.get('complete_sha256',r.get('replay_complete_sha256'))
            else: child.append(n)
        elif any(t in n for t in ['paired_tree_plan/actual_producer_attempt_1/', 'paired_tree_plan/actual_replay_attempt_1/', 'four_tree_matching_plan/attempt_1/', 'range_bound_feasibility/four_tree_matching/attempt_1/']):
            inherited.append(n)
    assert len(child)==60 and len(inherited)==4
    additions=sorted(set(rows)-set(original))
    for n in additions:
        if n in aliases['source_archives']:continue
        assert Path(n).suffix in {'.json','.md','.py'},n
        read(PROJECT/n,rows[n]['sha256'])
    qa_name='submission_revision_20260908/renewed_manuscript_v9/work/FINAL_TECHNICAL_QA_v9.json'
    qa=json.loads(read(PROJECT/qa_name,rows[qa_name]['sha256']))
    assert {r['external_runtime_not_packaged']:r['sha256'] for r in external} == qa['external_readonly_files']
    for n in ['resolve_selection.py','resolve_snapshots.py','plan_inventory.py','PLAN.md']:
        read(BASE/n)
    return {'status':'PASS_METADATA_SOURCE_SCOPE_ONLY','record_count':1644,'stat_bytes':934080471,
      'original_rows':len(original),'unchanged_nonalias_rows':preserved,'alias_paths':sorted(alias_paths),
      'exact_source_bindings':aliases['bindings'],'source_members_verified':source_members,
      'external_exclusions':external,'unknown_unresolved_record_types':0,
      'external_exclusions_equal_actual_qa_map':True,
      'metadata_json_authenticated':len(metadata),'fresh_child_receipts':len(child),
      'inherited_receipts':inherited,'declared_output_links_present':output_links,
      'added_paths':additions,'source_metadata_sha256':READS,
      'scientific_payloads_read':False,'payload_hashes_verified':False,'actual_create_approved':False}

if __name__=='__main__':
    print(json.dumps(main(),indent=2))
