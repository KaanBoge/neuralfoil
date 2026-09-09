"""Future metadata freeze requires explicitly selected complete barrier pins.

Not run: no sixteen-context four-tree completion exists at implementation time.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import four_barrier
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
FILES=('run.py','storage.py','four_barrier.py','adapter.py','study_inputs.py','legacy_results.py','study.py','prepare_freeze.py','test_downstream.py','README.md','SYNTHETIC_FAILURE_1.md','synthetic_failure_1_test_downstream.py','SOURCE_REVIEW.json','SOURCE_DIFF.patch')
def read(path,pin):
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('symlink')
    b=path.read_bytes()
    if hashlib.sha256(b).hexdigest()!=pin:raise ValueError('explicit selected pin')
    return b
def build(selection):
    if set(selection)!={'four_tree','paired_results'}:raise ValueError('explicit finite barrier selection')
    four_barrier.validate_registry(selection)
    paired=selection['paired_results'];old=json.loads(read(ROOT/paired['root']/'REGISTRY.json',paired['registry_sha256']))
    d=copy.deepcopy(old);d.update(selection);d['status']='SOURCE_REVIEW_REQUIRED_NO_EXECUTION_AUTHORITY'
    # Authenticate complete metadata identities without parsing scientific members.
    f=selection['four_tree'];folder=ROOT/f['root']
    cr=json.loads(read(folder/'REGISTRY_v3.json',f['registry_sha256']))
    for ph,key in [('certificates_produce','producer'),('certificates_replay','replay')]:
        r=json.loads(read(folder/ph/'COMPLETE.json',f[key+'_sha256']))
        if r.get('status')!='COMPLETE' or r.get('registry_sha256')!=f['registry_sha256'] or r.get('approval_sha256')!=f[key+'_approval_sha256'] or set(r['contexts'])!=set(old['contexts']):raise ValueError('complete sixteen context barrier required')
        read(folder/('ROOT_'+ph.upper()+'_APPROVAL.json'),f[key+'_approval_sha256'])
    if cr['sources']['context_support.py']!=f['context_support_sha256']:raise ValueError('support source')
    for phase,e in paired['phases'].items():
        read(ROOT/paired['root']/phase/'COMPLETE.json',e['complete_sha256']);read(ROOT/e['approval_path'],e['approval_sha256'])
    for n,h in old['sources'].items():read(ROOT/paired['root']/n,h)
    for n,h in old['provenance'].items():
        four_barrier.relative(n);read(ROOT/paired['root']/n,h)
    d['sources']={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in FILES}
    d['entrypoint_sha256']=d['sources']['run.py']
    d['provenance']={}
    d['external_sources'].update({str((ROOT/paired['root']/n).relative_to(ROOT)):h for n,h in old['sources'].items()})
    d['external_sources'].update({str((ROOT/paired['root']/n).relative_to(ROOT)):h for n,h in old['provenance'].items()})
    d['external_sources'][f['root']+'/context_support.py']=f['context_support_sha256']
    proposal=HERE.parent/'FOUR_CONTEXT_DOWNSTREAM_PROPOSAL.md'
    d['external_sources'][str(proposal.relative_to(ROOT))]=hashlib.sha256(proposal.read_bytes()).hexdigest()
    d['output_roots']=old['output_roots']+[f['root']+'/'+p for p in ['certificates_produce','certificates_replay']]+[str((HERE/p).relative_to(ROOT)) for p in ['preflight','calibrate','score','assess','execution_evidence']]
    references=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half','qualified_generic_harm_001','qualified_structural_harm_001','qualified_generic_kl_harm_001','qualified_structural_kl_harm_001','qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001']
    d.update(new_labels=['qualified_four_D_harm_001','qualified_four_D_kl_harm_001'],bootstrap_references=references,harm_reference_count=12,new_scalar_count=32,panel_record_count=651,bootstrap_record_count=420,harm_record_count=7812)
    return d
def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);args=p.parse_args()
    out=HERE/'REGISTRY.json'
    if out.exists():raise FileExistsError('freeze exists')
    selection=json.loads(read(Path(args.selection),args.selection_sha256));d=build(selection)
    selected=str(Path(args.selection).resolve().relative_to(ROOT))
    d['source_selection']={'path':selected,'sha256':args.selection_sha256}
    d['external_sources'][selected]=args.selection_sha256
    with out.open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
