from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent;REV=P.parents[3];ROOT=REV.parent;E=REV/'renewed_manuscript_v7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins={}
for name in ['DISPLAY_MANIFEST.json','METHOD_DIAGRAM.json']:
    w=json.loads((E/'work/displays'/name).read_text())
    for rel,h in w.get('source_sha256',{}).items():
        p=ROOT/rel;assert sha(p)==h;pins[str(p)]=h
    for rel,h in w['outputs'].items():
        p=E/rel;assert sha(p)==h;pins[str(p)]=h
# Reauthenticate all previously consumed pinned files after the review.
for p,h in json.loads((P/'CHECKS.json').read_text())['input_sha256'].items():assert sha(Path(p))==h
result={'status':'PASS_REAUTHENTICATED','additional_display_pins':pins,
 'owned_evidence_sha256':{p.name:sha(p) for p in P.iterdir() if p.is_file()},
 'main_source_sha256':sha(E/'main.complete.md'),'supplement_source_sha256':sha(E/'supplement.complete.md')}
target=P/'FINAL.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
print(sha(target))
