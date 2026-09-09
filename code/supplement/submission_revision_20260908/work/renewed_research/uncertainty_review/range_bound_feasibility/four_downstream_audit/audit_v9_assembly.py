"""Saved-text preservation audit; no assembler imports or scientific execution."""
from pathlib import Path
import hashlib,json,re
P=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
V=P/'submission_revision_20260908/renewed_manuscript_v9'
HERE=Path(__file__).parent
pins={}
def read(p,sha=None):
    b=p.read_bytes(); h=hashlib.sha256(b).hexdigest()
    if sha: assert h==sha,(str(p),h,sha)
    pins[str(p.relative_to(P))]=h
    return b
def text(p,sha=None): return read(p,sha).decode()
def tables(s):
    out=[]; rows=[]
    for l in s.splitlines()+['']:
        if l.startswith('|'): rows.append(l)
        elif rows: out.append('\n'.join(rows)); rows=[]
    return out
def caps(s): return [l for l in s.splitlines() if re.match(r'^Table [A-Z]*\d+\.',l)]
def subseq(a,b):
    pos=0
    for x in a:
        while pos<len(b) and b[pos]!=x: pos+=1
        assert pos<len(b),x[:100]
        pos+=1
c=json.loads(read(V/'work/ROOT_ASSEMBLY_CONFIG_v1_attempt2.json','310bac121ea86fd6e57817622fb28c224f14ac0ebf5110813f5eb58534beaa25'))
assert len(c['inputs'])==32
t={k:read(P/v['path'],v['sha256']) for k,v in c['inputs'].items()}
m=text(V/'main.complete.md','afb27cf203ca9b00767aca6af41fe7d4cd40fa09cdb4deb83621a1b47d423df0')
s=text(V/'supplement.complete.md','227f8046ff5e3e0be60d73e24820b340760b4f4c38e04db68c01234675c82178')
read(V/'work/ASSEMBLY.json','eb429f94a5c8be914789b5c0ca333341a634dad3561801d9a2bdcd518980c47f')
read(V/'assemble_submission.py','b544ff3999bde7a7807b145088f4bfc375f21285fe685cc52f8db2fb1c3a02a1')
assert m==t['main'].decode()
counts={}
for name,new,old in [('main',m,t['v8_main'].decode()),('supplement',s,t['v8_supplement'].decode())]:
    subseq(tables(old),tables(new)); subseq(caps(old),caps(new))
    oldrefs=old[old.index('# References'):]
    assert new[new.index('# References'):]==oldrefs+t['reference_addendum'].decode()
    assert re.findall(r'^\[(\d+)\]',oldrefs,re.M)==list(map(str,range(1,22)))
    assert re.findall(r'^\[(\d+)\]',new[new.index('# References'):],re.M)==list(map(str,range(1,24)))
    assert text(V/f'work/assembly_versions/v1/{name}.complete.md')==new
    counts[name]={'old_tables':len(tables(old)),'new_tables':len(tables(new)),'old_captions':len(caps(old)),'new_captions':len(caps(new))}
newtables=[]
for spec in c['tokens'].values():
    block=t[spec['input']].decode(); bt=tables(block)
    assert len(bt)==3
    if spec['p2_label_map']:
        rows=bt[1].splitlines()
        for i in range(2,len(rows)):
            cells=rows[i].split('|')
            for a,b in spec['p2_label_map']: cells[1]=cells[1].replace(a,b)
            rows[i]='|'.join(cells)
        bt[1]='\n'.join(rows)
    for b in bt: assert b in tables(s)
    for old,new in spec['caption_renames']:
        line=next(l for l in caps(block) if l.startswith('Table '+old+'.'))
        assert line.replace('Table '+old+'.','Table '+new+'.',1) in caps(s)
    newtables+=bt
assert len(newtables)==9
assert not re.search(r'@@[A-Z_]+@@',s+m)
# Authenticate already-completed independent numerical witnesses, without rerunning them.
for folder,sha in [('calibration_attempt_2','a51bdd848c20af54a7b859717d4afd04098dcd28eedf71f0c44578c350cfd141'),('score_attempt_1','9850951248ca768acca0500c109d44b0842e86f4c7297dfb88d55bf5ee6cd8df'),('assessment_attempt_2','44fc4471413e0327eea223f47f09c82105a927b06c75289ee338761578ab90fb')]:
    read(HERE/folder/'QA.json',sha); read(HERE/folder/'REVIEW.md')
read(Path(__file__))
for p,h in list(pins.items()): assert hashlib.sha256((P/p).read_bytes()).hexdigest()==h
out={'status':'PASS','scope':'saved source preservation and authenticated existing numerical witnesses; no visual review or scientific rerun','inputs':32,'reference_prefix':21,'new_references':2,'new_display_tables':9,'counts':counts,'pins':pins,'diagnostic':'An exploratory config display command first treated its inputs mapping as a list and raised KeyError; no artifact or scientific data changed.'}
with (HERE/'V9_ASSEMBLY_QA.json').open('x') as f: json.dump(out,f,indent=2); f.write('\n')
print(json.dumps({k:v for k,v in out.items() if k!='pins'}))
