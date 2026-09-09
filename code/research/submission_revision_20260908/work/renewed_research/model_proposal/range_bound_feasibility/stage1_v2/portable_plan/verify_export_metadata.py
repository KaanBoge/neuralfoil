"""Root metadata/code verification; never materializes empirical NPZ members."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import time

HERE=Path(__file__).resolve().parent
REGISTRY='dc17af0ed1a5211e21d2dc0dc0f015624a4366c4b051584e509ff3f8e1e229e0'
ARCHIVE='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
INNER='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'


def checked(path,pin):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('hash mismatch: '+str(path))
    return raw


def main():
    start=time.monotonic()
    r=json.loads(checked(HERE/'REGISTRY_v3.json',REGISTRY))
    for name,pin in r['implementation_sha256'].items():
        checked(HERE/name,pin)
    source=checked(HERE/'integrity.py',r['implementation_sha256']['integrity.py'])
    spec=importlib.util.spec_from_loader('root_integrity',loader=None)
    helper=importlib.util.module_from_spec(spec)
    exec(compile(source,'<pinned integrity>','exec'),helper.__dict__)
    payload,manifest=helper.verified_members(HERE/'qualified_harm_private_v1.zip',ARCHIVE,INNER)
    inventory=json.loads(payload['inventory.json'])
    if len(payload)!=140 or len(inventory['contexts'])!=16 or len(inventory['native_contexts'])!=18:
        raise ValueError('finite inventory')
    if inventory['new_fits']!=0 or inventory['rows']!=29856 or inventory['panels']!=31 or not inventory['features_included']:
        raise ValueError('study scope inventory')
    expected_labels=['qualified_structural_harm_001','qualified_generic_harm_001']
    if inventory['labels']!=expected_labels:
        raise ValueError('fixed candidates')
    for context in inventory['contexts']:
        for member in [f'calibration/{context}.npz',f'roles/{context}.json',f'trees/{context}.npz']:
            if member not in payload:
                raise ValueError('missing context member')
        for label in expected_labels:
            if f'scalars/{label}_{context}.json' not in payload:
                raise ValueError('missing scalar')
    for context in inventory['native_contexts']:
        if f'native/{context}.npz' not in payload:
            raise ValueError('missing native context')
    witness=json.loads(payload['SOURCE_WITNESS.json'])
    if witness['inputs']!=r['inputs']:
        raise ValueError('input provenance')
    counts={'CSV_loads':0,'NPZ_loads':0,'NPZ_member_materializations':0}
    for event in witness['actual_data_reads']:
        if not event['source_paths'] or any(r['inputs'].get(p)!=event['sha256'] for p in event['source_paths']):
            raise ValueError('unregistered reader event')
        if event['reader']=='pandas.read_csv':
            counts['CSV_loads']+=1
            if event['rows']<0 or not event['columns']:
                raise ValueError('CSV event schema')
        elif event['reader']=='numpy.load':
            counts['NPZ_loads']+=1
            for member in event['members']:
                counts['NPZ_member_materializations']+=1
                if member['bytes']<0 or not member['name'] or not member['dtype']:
                    raise ValueError('member event schema')
        else:
            raise ValueError('unsupported actual reader')
    if counts!={'CSV_loads':71,'NPZ_loads':53,'NPZ_member_materializations':1253}:
        raise ValueError('actual read counts')
    schema=json.loads(payload['scoring/schema.json'])
    if schema['rows']!=29856 or len({x['name'] for x in schema['columns']})!=len(schema['columns']):
        raise ValueError('typed frame schema metadata')
    packaged={}
    for name in ['policy','codec','metrics']:
        for node in ast.parse(payload[f'code/{name}.py']).body:
            if isinstance(node,ast.FunctionDef):
                packaged[node.name]=node
    renamed={'exact_group_means':'group_means_exact','synthetic_confidence':'calibrate_exact_groups'}
    for item in witness['functions']:
        original_paths=[Path(p) for p,h in r['inputs'].items() if h==item['source_sha256'] and Path(p).suffix=='.py']
        if not original_paths:
            raise ValueError('source AST origin')
        raw=checked(original_paths[0],item['source_sha256'])
        node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==item['function'])
        digest=lambda value:hashlib.sha256(ast.dump(value,include_attributes=False).encode()).hexdigest()
        if digest(node)!=item['original_AST_sha256']:
            raise ValueError('original function AST')
        output=packaged[renamed.get(node.name,node.name)]
        if digest(output)!=item['packaged_AST_sha256']:
            raise ValueError('packaged function AST')
        if item['permitted_adapter']=='name/docstring only':
            if ast.dump(ast.Module(body=node.body[1:],type_ignores=[]),include_attributes=False)!=ast.dump(ast.Module(body=output.body[1:],type_ignores=[]),include_attributes=False):
                raise ValueError('production body changed')
        elif digest(node)!=digest(output):
            raise ValueError('unchanged body mismatch')
    report={'status':'PASS_METADATA_AND_CODE_PROVENANCE_ONLY','archive_sha256':ARCHIVE,
        'manifest_sha256':INNER,'registry_sha256':REGISTRY,'payloads':len(payload),
        'reader_counts':counts,'typed_frame_columns':len(schema['columns']),
        'AST_functions_verified':len(witness['functions']),'empirical_NPZ_members_materialized':0,
        'fresh_extraction_or_numeric_replay':False,'seconds':time.monotonic()-start,
        'scope':'Private archive authentication and metadata/source audit; not numerical replay success or data rights approval.'}
    raw=json.dumps(report,indent=2)+'\n'
    with (HERE/'ROOT_EXPORT_METADATA_QA.json').open('x') as stream:
        stream.write(raw)
    print(raw)


if __name__=='__main__':
    main()
