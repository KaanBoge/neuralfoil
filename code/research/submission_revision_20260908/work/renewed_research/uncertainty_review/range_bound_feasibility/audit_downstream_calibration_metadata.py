"""Supplementary metadata-only inventory checks; no NPZ members materialized."""
import json,collections,zipfile,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
P=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
def sha(b):return hashlib.sha256(b).hexdigest()
def obj(p):return json.loads(p.read_bytes())
reg=obj(P/'REGISTRY.json');ev=obj(P/'calibrate/ACCESS.json');ap=obj(P/'ROOT_CALIBRATE_APPROVAL.json');rec=obj(P/'calibrate/COMPLETE.json')
assert ap['actual_execution_authorized'] is True and ap['workers']==1 and ap['seconds']==900
assert ap['contexts']==reg['contexts'] and ap['output_roots']==reg['output_roots'] and ap['logical_cap']==reg['logical_cap'] and ap['failure_reserve']==reg['failure_reserve']
es=[x for x in ev if x.get('operation')=='JSON parse' and 'origin' in x]
expected=[('parent',f'roles/{c}.json') for c in reg['contexts']]+[('parent',f'scalars/qualified_structural_harm_001_{c}.json') for c in reg['contexts']]+[('KL addon',f'scalars/qualified_structural_kl_harm_001_{c}.json') for c in reg['contexts']]
assert collections.Counter((x['origin'],x['member']) for x in es)==collections.Counter(expected)
for origin,path in [('parent',ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'),('KL addon',ROOT/'model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip')]:
    with zipfile.ZipFile(path) as z:
        mn=next(n for n in z.namelist() if n.endswith('manifest.json'));prefix=mn[:-13];manifest=json.loads(z.read(mn))['files']
        for x in es:
            if x['origin']==origin:assert x['sha256']==manifest[x['member']]['sha256']==sha(z.read(prefix+x['member']))
qa=obj(HERE/'DOWNSTREAM_CALIBRATION_QA.json');assert sha((HERE/'DOWNSTREAM_CALIBRATION_QA.json').read_bytes())=='32226ecfa6a12d748580d5bddb14d3d2c1898fe55c05d1726e1e13ea72d82b65'
stats={}
for kind in ['H','KL']:
    rs=[x for x in qa['records'] if x['kind']==kind]
    stats[kind]={'U_strict_decrease':sum(x['U_decreased_exact'] for x in rs),'t_strict_increase':sum(x['t_increased_exact'] for x in rs),'t_strict_decrease':sum(x['t_decreased_exact'] for x in rs),'tU_exact_sign_counts':dict(collections.Counter(str(x['tU_change_exact_sign']) for x in rs))}
r={'status':'PASS_METADATA_SUPPLEMENT','complete_sha256':sha((P/'calibrate/COMPLETE.json').read_bytes()),'archive_JSON_parses':48,'parent_JSON_parses':32,'addon_JSON_parses':16,'no_array_materialization_in_this_supplement':True,'comparisons':stats}
with (HERE/'DOWNSTREAM_CALIBRATION_METADATA_QA.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r,indent=2))
