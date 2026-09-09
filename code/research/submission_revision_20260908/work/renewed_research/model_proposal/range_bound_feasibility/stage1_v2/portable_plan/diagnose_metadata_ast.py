"""Read-only diagnosis of AST metadata failure, no numerical data loading."""
from pathlib import Path
import ast,hashlib,json,zipfile

HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'REGISTRY_v3.json').read_bytes())
with zipfile.ZipFile(HERE/'qualified_harm_private_v1.zip') as z:
    w=json.loads(z.read('SOURCE_WITNESS.json'))
for item in w['functions']:
    paths=[Path(p) for p,h in r['inputs'].items() if h==item['source_sha256'] and Path(p).suffix=='.py']
    raw=paths[0].read_bytes()
    assert hashlib.sha256(raw).hexdigest()==item['source_sha256']
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==item['function'])
    digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    print(json.dumps({'function':item['function'],'source':str(paths[0]),'actual_AST':digest,
        'recorded_AST':item['original_AST_sha256'],'equal':digest==item['original_AST_sha256']}))
