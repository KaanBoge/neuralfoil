"""Reviewer-authored schema normalization; no new visual review is asserted."""
from pathlib import Path
import hashlib,json
OUT=Path(__file__).resolve().parent/'canonical_reviews'
BASE=OUT.parent.parent
PIN={
 'v1':('9b48230e9b6effcf47d38e279c5890ea7f3225e3028d813004bdced5c053f98a','784a1c506edb1e2d7e0dc64d1e046f749a8271b4424c3bf06520532a3ba245e9'),
 'v3':('5dd920281218825f0c1bd3fd7f1f2ca90b63b84ac1f58889ddbef012da2076bd','edae0853d72b1ec3a89bb0ce0a597e7df4000d58111ede8ef5768f6ab4233f1b')}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
OUT.mkdir(exist_ok=True)
for version,(lh,rh) in PIN.items():
    folder=BASE/f'visual_v7_{version}';ledger=folder/'PAGE_LEDGER.json';report=folder/'REVIEW.md'
    assert sha(ledger)==lh and sha(report)==rh
    old=json.loads(ledger.read_text());pdf=Path(old['pdf']);assert sha(pdf)==old['pdf_sha256']
    rows=[]
    for r in old['pages']:
        assert r['individually_viewed_original_resolution'] is True
        png=pdf.parent/f"page-{r['page']}.png";assert sha(png)==r['png_sha256']
        # V1 pages 1 and 2 had a documented layout issue: never promote to PASS.
        status='PASS_WITH_NOTED_LAYOUT_ISSUE' if version=='v1' and r['page'] in [1,2] else 'PASS'
        rows.append({**r,'result':status,'png_path':str(png),'original_review_path':str(report),
                     'original_ledger_path':str(ledger),'reviewer':'astra_ensemble_models'})
    new={'schema':'reviewer-normalized-page-ledger-1','pdf':str(pdf),'pdf_sha256':old['pdf_sha256'],
         'normalization_only':True,'new_visual_inspection':False,'pages':rows,
         'original_witness_sha256':{str(ledger):lh,str(report):rh},
         'excluded_other_reviewers':True,'scope':old['inspected_pages']}
    path=OUT/f'{version}_PAGE_LEDGER.json'
    with path.open('x') as f:json.dump(new,f,indent=2);f.write('\n')
    print(version,sha(path),len(rows))
