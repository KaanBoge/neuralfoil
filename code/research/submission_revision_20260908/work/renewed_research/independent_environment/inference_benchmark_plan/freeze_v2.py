"""Source-only successor registry; no numerical arrays or requests are opened."""
from pathlib import Path
import hashlib,json
from serving import ROUTES,QUALIFIED,COHORTS
from timing import schedule
from loader_v2 import FEATURE,ORIGINAL,PREPARED,PARENT,ADDON
H=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    oldraw=(H/'REGISTRY.json').read_bytes()
    assert sha(oldraw)=='61c95ce3af8e958c8ba6bfeff00a13cc16ed133de96fc9f12c63003c99e99dbf'
    old=json.loads(oldraw)
    for n,h in old['sources'].items():assert sha((H/n).read_bytes())==h
    root=H.parents[4]
    for n,h in old['files'].items():assert sha((root/n).read_bytes())==h
    for n,s in old['archives'].items():assert sha((root/n).read_bytes())==s['sha256']
    scopes={}
    features=['alpha','Re','airfoil','X9','X16','X24','X44','X62','K18','BASE_CD','XLARGE_CD','all_model_CD','all_model_CL']+['ncrit_'+k for k in ['CD','CL','confidence','Top_Xtr','Bot_Xtr']]
    for route in ['all',*ROUTES]:
        allroutes=route=='all';isoriginal=allroutes or route==ROUTES[2];isqualified=allroutes or route in QUALIFIED
        files={n:h for n,h in old['files'].items() if n.startswith(FEATURE)}
        if isoriginal:
            files.update({n:old['files'][n] for n in [PREPARED,ORIGINAL+'experimental_policies.json',ORIGINAL+'inference_references.npz']})
        archives={};arrays={}
        for c in COHORTS:arrays[FEATURE+f'data/{c}.npz']=features if allroutes else ['alpha','Re','airfoil']
        if isoriginal:arrays[ORIGINAL+'inference_references.npz']=[c+'_'+k for c in COHORTS for k in (['gate','unpenalized_transfer','BASE_CD','X62','all_model_CD'] if allroutes else ['gate'])]
        if isqualified:
            names=['code/qualified_numerics.py','code/policy.py','code/evaluator.py','trees/final.npz']+[f'native/{c}.npz' for c in COHORTS]
            names += [f'scalars/{k}_final.json' for k in QUALIFIED[:2] if allroutes or k==route]
            archives[PARENT]={**old['archives'][PARENT],'members':{n:old['archives'][PARENT]['members'][n] for n in names}}
            arrays[PARENT+'!trees/final.npz']=['initial','nodes_offsets','nodes','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets']
            for c in COHORTS:arrays[PARENT+f'!native/{c}.npz']=(['indices','BASE_CD','core','anchor','gate']+[k+s for k in QUALIFIED[:2] for s in ['', '__strength','__effective_fraction','__intervened']]) if allroutes else ['gate']
            if allroutes or '_kl_' in route:
                names=[f'scalars/{k}_final.json' for k in QUALIFIED[2:] if allroutes or k==route]
                if allroutes:names += [f'predictions/{c}.npz' for c in COHORTS]
                archives[ADDON]={**old['archives'][ADDON],'members':{n:old['archives'][ADDON]['members'][n] for n in names}}
                if allroutes:
                    for c in COHORTS:arrays[ADDON+f'!predictions/{c}.npz']=['indices']+[k+s for k in QUALIFIED[2:] for s in ['', '__strength','__effective_fraction','__intervened']]
        scopes[route]={'files':files,'archives':archives,'arrays':arrays}
    sources=['PLAN.md','serving.py','timing.py','README_v2.md','provenance_v2.py','loader_v2.py','measurement_v2.py','watchdog_v2.py','runner_v2.py','freeze_v2.py','test_v2.py']
    result={'status':'SOURCE_ONLY_REVIEW_REQUIRED_NO_ACTUAL_APPROVAL','v1_registry_sha256':sha(oldraw),'v1_sources':old['sources'],'sources':{n:sha((H/n).read_bytes()) for n in sources},'scopes':scopes,'routes':list(ROUTES),'schedule':schedule(),'workload_rows':{'SG_exposed':242,'W_new_challenge':255},'runtime':'/opt/anaconda3/bin/python','max_seconds':600,'max_request_seconds':60,'max_rss_bytes':2*1024**3,'max_output_bytes':1024**3,'cold_repeats':1,'warmups':2,'warm_repeats':7,'workers':1,'source_stage_numerical_arrays_opened':False}
    with (H/'REGISTRY_v2.json').open('x') as f:json.dump(result,f,indent=2)
    print(sha((H/'REGISTRY_v2.json').read_bytes()))
if __name__=='__main__':main()
