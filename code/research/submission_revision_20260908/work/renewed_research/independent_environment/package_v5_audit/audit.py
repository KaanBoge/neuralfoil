"""Independent manifest/role/link audit. Hashes scientific archives, never parses them."""
from pathlib import Path
import hashlib,json,re,time
H=Path(__file__).resolve().parent
PROJECT=next(p for p in H.parents if p.name=='NeuralFoil_Research_Paper')
PKG=H.parent/'package_v5_fresh_extraction_v1/NeuralFoil_Private_Submission_Package_v5'
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    start=time.monotonic();out=H/'AUDIT.json'
    if out.exists():raise FileExistsError('preserve audit')
    assert SHA(PKG/'MANIFEST.json')=='9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9'
    assert SHA(PKG/'INPUT_MANIFEST.json')=='0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8'
    m=json.loads((PKG/'MANIFEST.json').read_text());i=json.loads((PKG/'INPUT_MANIFEST.json').read_text())
    assert len(m['files'])==433 and len(i['files'])==432
    actual={p.relative_to(PKG).as_posix() for p in PKG.rglob('*') if p.is_file()};assert actual==set(m['files'])|{'MANIFEST.json'}
    for p in PKG.rglob('*'):assert not p.is_symlink()
    for n,d in m['files'].items():assert SHA(PKG/n)==d['sha256'] and (PKG/n).stat().st_size==d['bytes'],n
    rows=i['files'];byrole=lambda role:[r for r in rows if r['role']==role]
    qa=json.loads((PKG/'quality/FINAL_TECHNICAL_QA.json').read_text());assert SHA(PKG/'quality/FINAL_TECHNICAL_QA.json')=='ac58346bdc55f51370197788354319ead001f4ae0cbe90ea810b693f3c6fe2b7'
    assert qa['status']=='PASS_TECHNICAL_PREPARATION'
    docs={}
    for kind,pages in [('main',30),('supplement',80)]:
        assert qa['documents'][kind]['pages']==pages and len(qa['documents'][kind]['visual'])==pages
        assert {r['page'] for r in qa['documents'][kind]['visual']}==set(range(1,pages+1))
        for ext in ['pdf','docx','source']:
            r,=byrole(kind+'_'+ext);key='reading_source' if kind=='supplement' and ext=='source' else ext
            art=qa['documents'][kind]['artifacts'][key]
            assert r['sha256']==art['sha256']==qa['files'][r['qa_key']]==SHA(PKG/r['target'])==SHA(Path(art['path']))
            docs[r['target']]=r['sha256']
    figures=byrole('figure');aliases=byrole('source_image_alias')
    expected={(s,e) for s in i['requirements']['figure_ids'] for e in ['png','svg','pdf']}
    assert len(figures)==18 and {(r['id'],r['format']) for r in figures}==expected and len(aliases)==6
    for r in figures+aliases:assert qa['files'][r['qa_key']]==r['sha256']
    for r in aliases:assert SHA(PKG/r['target'])==SHA(PKG/'figures'/Path(r['target']).name)
    images=[]
    for name in ['manuscript/main.md','manuscript/supplement.md']:
        text=(PKG/name).read_text();assert 'NAVIGATION_PLACEHOLDER' not in text
        for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):
            p=(PKG/name).parent/link;assert p.is_file();images.append({'source':name,'link':link,'sha256':SHA(p)})
    assert len(images)==6
    archive_rows=byrole('private_archive');assert len(archive_rows)==8
    old=PROJECT/i['legacy_witness']['source'];assert SHA(old)==i['legacy_witness']['sha256']=='a14fcee7c9ea63629395d150baa3e1006e841c3de321dc94834c6acde3f95854'
    prior=json.loads(old.read_text());legacy=[]
    for r in archive_rows:
        if 'legacy_member' in r:assert prior['files'][r['legacy_member']]['sha256']==r['sha256'];legacy.append(r['id'])
    assert set(legacy)==set(i['requirements']['legacy_archive_ids']) and len(legacy)==6
    for archive_id,pin in [('qualified_harm','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'),('qualified_kl_harm','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b')]:
        r,=[x for x in archive_rows if x['id']==archive_id];assert r['sha256']==pin
    assert {r['qa_key'] for r in byrole('review')}==set(qa['review_files'])
    guide_links=[]
    for name in ['README.md','NAVIGATION.md','PERMISSIONS.md','REPLAY_GUIDE.md','author_approval/AUTHOR_CHECKLIST.md']:
        for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',(PKG/name).read_text()):
            if '://' not in link:
                assert ((PKG/name).parent/link.split('#')[0]).exists();guide_links.append([name,link])
    for r in rows:
        assert not any(x in r['source'].lower() for x in ['all_context','downstream','inference_benchmark'])
    result={'status':'PASS_INTEGRITY_AND_BINDINGS_WITH_NONBLOCKING_NAVIGATION_NOTE','seconds':time.monotonic()-start,'payload_count':433,'input_records':432,'publication_identities':docs,'figure_formats':18,'PNG_aliases':6,'markdown_images':images,'archives':[{k:r[k] for k in ['id','target','sha256']} for r in archive_rows],'unchanged_legacy_archives':legacy,'reviewed_page_bindings':110,'review_files':len(qa['review_files']),'guide_relative_links':guide_links,'note':'NAVIGATION earlier evidence row should point to historical/v4/evidence, not evidence; no package edits','scientific_members_parsed':False,'inner_replay_executed':False,'manifest_sha256':SHA(PKG/'MANIFEST.json'),'audit_source_sha256':SHA(Path(__file__))}
    with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
if __name__=='__main__':main()
