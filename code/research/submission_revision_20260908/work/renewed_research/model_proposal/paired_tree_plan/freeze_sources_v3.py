"""V3 metadata freeze with exact V2 preservation and resource-only AST witness."""
import ast,json
import support as s

def functions(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}

def main():
    oldraw=(s.HERE/'REGISTRY_v2.json').read_bytes()
    if s.digest(oldraw)!='4ce4f86e3ef545c0d588cec02d7a8926a32e8ba237871ff3d6f0e85cbc3adc0f':raise ValueError('V2 registry identity')
    old=json.loads(oldraw);delta={}
    allowed={'runner.py','replay_wrapper.py','test_wrapper.py','verify_wrapper_synthetic.py'}
    for name,pin in old['sources'].items():
        before=(s.HERE/('v2_snapshot/'+name if not name.endswith('.json') else name)).read_bytes()
        after=(s.HERE/name).read_bytes()
        if s.digest(before)!=pin:raise ValueError('V2 snapshot mismatch '+name)
        if before!=after and name not in allowed:raise ValueError('unexpected source change '+name)
        delta[name]={'before_sha256':pin,'after_sha256':s.digest(after),'byte_identical':before==after}
    astsame={}
    for name in ('runner.py','replay_wrapper.py'):
        before=(s.HERE/'v2_snapshot'/name).read_bytes();after=(s.HERE/name).read_bytes()
        a,b=functions(before),functions(after)
        if set(a)!=set(b):raise ValueError('function inventory changed')
        for key in a:
            if key=='execute':
                normalized=after.replace(b'REGISTRY_v3.json',b'REGISTRY_v2.json')
                if functions(normalized)[key]!=a[key]:raise ValueError('nonregistry execute change')
            elif a[key]!=b[key]:raise ValueError('function body changed '+key)
        astsame[name]=list(a)
    # Exact module substitution must be only cap/comment and registry filename.
    before=(s.HERE/'v2_snapshot/replay_wrapper.py').read_bytes()
    after=(s.HERE/'replay_wrapper.py').read_bytes()
    expected=before.replace(b'LIMIT=128*2**20',b'LIMIT=256*2**20  # ROOT_MEMORY_AMENDMENT.md; wrapper only, producer remains128MiB').replace(b'REGISTRY_v2.json',b'REGISTRY_v3.json')
    if after!=expected:raise ValueError('wrapper changes exceed approved cap/wiring')
    note=(s.HERE/'ROOT_MEMORY_AMENDMENT.md').read_bytes()
    if s.digest(note)!='6994856bb7ee362c4db488f67324d40cebc8fcf23a0bd7573aec5a212fee54fc':raise ValueError('amendment identity')
    diff={'parent_registry_sha256':s.digest(oldraw),'amendment_sha256':s.digest(note),'sources':delta,'all_function_AST_unchanged_except_registry_literal':astsame,'memory_formula_unchanged':True,'producer_unchanged':True,'wrapper_limit_before':134217728,'wrapper_limit_after':268435456}
    diffsha=s.exclusive(s.HERE/'SOURCE_DIFF_v3.json',diff)
    sources={name:s.digest((s.HERE/name).read_bytes()) for name in old['sources']}
    for name in ('ROOT_MEMORY_AMENDMENT.md','V3_RESOURCE_RESULT.md','freeze_sources_v3.py'):sources[name]=s.digest((s.HERE/name).read_bytes())
    sources['SOURCE_DIFF_v3.json']=diffsha
    ledger=[]
    for rel,pin in old['dependencies'].items():s.read_pinned(s.ROOT/rel,pin,ledger,'source_or_metadata_freeze')
    evidence={str(p.relative_to(s.HERE)):s.digest(p.read_bytes()) for p in sorted((s.HERE/'wrapper_synthetic_attempt_2_v3').iterdir())}
    reg={'schema':'PAIRED_TREE_SOURCE_REGISTRY_V3','sources':sources,'dependencies':old['dependencies'],'input':old['input'],'scope':old['scope'],'parent_registry_sha256':s.digest(oldraw),'amendment_sha256':s.digest(note),'wrapper_synthetic_evidence':evidence,'preserved_failed_gate':old['wrapper_synthetic_evidence'],'wrapper_estimated_owned_cap_bytes':268435456,'producer_estimated_owned_cap_bytes':134217728,'real_execution_authorized':False,'model_members_materialized_by_freezer':0,'read_ledger':ledger}
    print(s.exclusive(s.HERE/'REGISTRY_v3.json',reg))

if __name__=='__main__':main()
