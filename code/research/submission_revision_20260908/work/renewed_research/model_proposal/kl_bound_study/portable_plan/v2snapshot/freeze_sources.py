"""Finite metadata/source registry; no NPZ/CSV arrays or target materialization."""
from pathlib import Path
import json,difflib
import integrity,shared
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent;ROOT=STUDY.parents[1]
def main():
    inputs={};evidence={}
    def meta(path,h):
        raw=path.read_bytes()
        if integrity.sha(raw)!=h:raise ValueError('metadata pin')
        inputs[str(path)]=h;return json.loads(raw)
    freeze=meta(STUDY/'IMPLEMENTATION_FREEZE_v2.json','fc44b641a13958487fa69e8655c29c30b43fbbcbc9c7fe986ace40de5e07ec08')
    inputs.update({str(STUDY/n):h for n,h in freeze['source_sha256'].items()});inputs.update(freeze['external_source_sha256'])
    for phase,h in {'preflight':'0bd2a520b5f5323461c0d8e3d2f70ece468cd921da7f8c4b14854e76bf667d6c','calibrate':'c3ea8ba1f3d5dc7f1aa0914db96e61a47052d4d67aaf93fce7efde2361f4b0b0','score':'ff0604357bdda4a321424380c77362c1e22a419979a798ba118b0865a98eb104','assess':'47c5a91da283e9e59ad51821e6661a54275946917c965a56d63c034d688bb01d'}.items():
        p=STUDY/phase/'COMPLETE.json';record=meta(p,h);evidence[phase+'_COMPLETE.json']=str(p)
        inputs.update({str(STUDY/phase/n):v for n,v in record['outputs'].items()})
    for n,h in {'ROOT_PREFLIGHT_APPROVAL.json':'de485d33777aa4cad93d62f135b3a29d680d8558aa462e40ba16605cfa57e01f',
        'ROOT_CALIBRATION_APPROVAL.json':'2dba04bf835a552c5b1ddd535e22d5ac363e0f784414d144d2d07d41eba407bf',
        'ROOT_SCORE_APPROVAL.json':'3de8d9a7d01b4cd56a1ed5e06b33518d311bb234d4b18ea059c96b6253b8ea19',
        'ROOT_ASSESSMENT_APPROVAL.json':'4176230c4c83d343753e9452ee234b28f3aab9892bdbc3d45de5fdcdacae0ef3'}.items():
        meta(STUDY/n,h);evidence[n]=str(STUDY/n)
    audit=ROOT/'uncertainty_review/range_bound_feasibility'
    for n,h in {'KL_ASSESSMENT_REVIEW.md':'a4d7d7bd7c35d49cc9db88b3f7db2319afaf0c851d24980f237f349a6a94d830',
        'KL_ASSESSMENT_QA.json':'2715410738eb1bc299e483a336633af15bbef3004a706981ea2c7f8013ba9173',
        'KL_SUMMARY_QA.json':'a7582927b70335f5e85b8246406168ebb3398b0bbbaef2271d4f35ce755b3923'}.items():
        raw=(audit/n).read_bytes()
        if integrity.sha(raw)!=h:raise ValueError('audit pin')
        inputs[str(audit/n)]=h;evidence[n]=str(audit/n)
    inputs[str(STUDY/'REPORT.md')]='2dd04c665c1aad9c9a879ee8c08bebcc48b45249330d271dce37cf370588165a';evidence['ORIGINAL_REPORT.md']=str(STUDY/'REPORT.md')
    for n in ['IMPLEMENTATION_FREEZE_v2.json','SOURCE_DIFF_v2.json']:
        evidence[n]=str(STUDY/n)
    inputs[str(HERE/'COMPLETED_REVIEW_NOTE.md')]=integrity.sha((HERE/'COMPLETED_REVIEW_NOTE.md').read_bytes());evidence['COMPLETED_REVIEW_NOTE.md']=str(HERE/'COMPLETED_REVIEW_NOTE.md')
    prior_raw=(HERE/'v1snapshot/REGISTRY.json').read_bytes()
    if integrity.sha(prior_raw)!='634bb45c07400abc0a43c61659d6f979430d81e411fba3a5b5cc4989476bdfd9':raise ValueError('v1 snapshot registry')
    prior=json.loads(prior_raw);delta={}
    for n,h in prior['sources'].items():
        old=(HERE/'v1snapshot'/n).read_bytes();new=(HERE/n).read_bytes()
        if integrity.sha(old)!=h:raise ValueError('v1 snapshot source')
        delta[n]={'prior_sha256':h,'successor_sha256':integrity.sha(new),'diff':''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='v1snapshot/'+n,tofile=n))}
    with (HERE/'SOURCE_DIFF_v2.json').open('x') as f:json.dump(delta,f,indent=2);f.write('\n')
    names=['PLAN.md','README.md','COMPLETED_REVIEW_NOTE.md','integrity.py','export_support.py','shared.py','build_replay.py','replay.py','test_portable.py','test_source_adapter.py','freeze_sources.py','SOURCE_HANDOFF.md','test_successor.py','SUCCESSOR_FAILURE_1.md','SUCCESSOR_HANDOFF.md','SOURCE_DIFF_v2.json']
    z={'status':'SOURCE_ONLY_AWAITING_REVIEW','sources':{n:integrity.sha((HERE/n).read_bytes()) for n in names},'inputs':inputs,'evidence':evidence,
        'parent_archive_sha256':shared.PARENT_SHA,'parent_manifest_sha256':shared.PARENT_MANIFEST,
        'counts':shared.COUNTS,'bootstrap_references':7,'harm_references':9,'real_export_or_replay':False,
        'preserved_registry_sha256':integrity.sha(prior_raw),'synthetic_tests':25}
    raw=json.dumps(z,indent=2).encode()+b'\n'
    with (HERE/'REGISTRY_v2.json').open('xb') as f:f.write(raw)
    print(integrity.sha(raw))
if __name__=='__main__':main()
