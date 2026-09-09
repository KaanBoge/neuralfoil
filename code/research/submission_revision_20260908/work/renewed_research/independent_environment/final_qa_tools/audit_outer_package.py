"""Independent final opaque archive/disk audit. No packaged code execution."""
import hashlib,json,time
from pathlib import Path
P=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
B=P/'submission_revision_20260908/work/renewed_research/uncertainty_review/package_v6_plan'
E=P/'submission_revision_20260908/renewed_manuscript_v9'
X=B/'outer_extract_attempt_1/NeuralFoil_Private_Submission_Package_v6'
def digest(p):
    h=hashlib.sha256();n=0
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b);n+=len(b)
    return h.hexdigest(),n
def main():
    start=time.monotonic();pins={}
    def auth(p,h):
        v,n=digest(p);assert v==h,str(p);pins[str(p)]=v;return n
    def meta(p,h):auth(p,h);return json.loads(p.read_bytes())
    archive=E/'deliverables/NeuralFoil_Private_Submission_Package_v6.zip'
    assert auth(archive,'d203b7e674711c53b557cd1a2746fa4b4008d4dc7cfca8a581e9e064092614f3')==263061372
    m=meta(X/'MANIFEST.json','a84869769cb8952e2e9e82f6ccf16489e5f6dba3a19ccb3b5d357329c6446149')
    im=meta(X/'INPUT_MANIFEST.json','1cbc550dcd5ee6fab83de13a61896582c2b89a3101af034a10f30f55e37a21f0')
    selection=meta(B/'OUTER_SELECTION_v1.json','6b5cdd33dab3ec0859632c1fee32b36b30949f1f006cc8755f4739356643e2d4')
    assert im['files']==selection['files'] and im['requirements']==selection['requirements']
    assert len(m['files'])==541 and len(im['files'])==540
    assert m['private'] is True and m['human_author_approval'] is False and m['public_release'] is False
    assert im['human_author_approval'] is False and im['public_release'] is False
    rows={r['target']:r for r in im['files']}
    assert set(m['files'])==set(rows)|{'INPUT_MANIFEST.json'}
    actual=set();total=0
    for p in X.rglob('*'):
        assert not p.is_symlink(),str(p)
        if p.is_file():actual.add(p.relative_to(X).as_posix())
    assert actual==set(m['files'])|{'MANIFEST.json'}
    for n,r in m['files'].items():
        p=X/n;h,count=digest(p)
        assert (h,count)==(r['sha256'],r['bytes']),n
        total+=count
        if n in rows:assert (h,count)==(rows[n]['sha256'],rows[n]['bytes'])
    assert sum(r['bytes'] for r in im['files'])==378482698
    assert total+(X/'MANIFEST.json').stat().st_size<536870912
    qa=meta(X/'quality/FINAL_TECHNICAL_QA.json','24282221edca95bfefe05e2add3f5974e49c406d6d68565d421f5faabb1bcc26')
    cfg=meta(X/'quality/FINAL_AUTHORIZED_CONFIG.json','419e75ceec4cf80b364572f0e776a40f2d6506a90178f79b794ad8b42a510642')
    assert qa['status']=='PASS_TECHNICAL_PREPARATION' and qa['external_readonly_files']==cfg['external_readonly_pins'] and len(qa['external_readonly_files'])==360
    docs=[];figures=[];archives=[]
    for n,r in rows.items():
        parts=Path(n).parts[:-1]
        assert not any(x.lower().startswith(('venv','conda')) or x.lower() in {'site-packages','pkgs','envs','.cache','__pycache__'} for x in parts)
        assert not Path(r['source']).is_absolute()
        if r['role'] in {'main_pdf','main_docx','main_source','supplement_pdf','supplement_docx','supplement_source'}:
            kind='main' if r['role'].startswith('main') else 'supplement';ext=Path(n).suffix
            key={'.pdf':'pdf','.docx':'docx','.md':'source' if kind=='main' else 'reading_source'}[ext]
            art=qa['documents'][kind]['artifacts'][key]
            assert r['sha256']==art['sha256'];docs.append(n)
        if r['role']=='figure':
            assert r['sha256']==qa['files'][r['qa_key']];figures.append(n)
        if r['role']=='private_archive':archives.append({k:r[k] for k in ['id','target','sha256','bytes']})
    assert len(docs)==6 and len(figures)==18 and len(archives)==9
    assert {r['id'] for r in archives}==set(im['requirements']['archive_ids'])
    aliases=[r for r in rows.values() if r['role']=='source_image_alias'];assert len(aliases)==6
    for r in aliases:assert digest(X/r['target'])==digest(X/'figures'/Path(r['target']).name)
    for path,h in list(pins.items()):assert digest(Path(path))[0]==h
    return {'status':'PASS_INDEPENDENT_FINAL_OPAQUE_INTEGRITY','pins':pins,'archive_bytes':263061372,
      'manifest_payloads':541,'disk_files_including_manifest':542,'selected_rows':540,'selected_bytes':378482698,
      'manifest_listed_bytes':total,'expanded_bytes_including_manifest':total+(X/'MANIFEST.json').stat().st_size,
      'current_documents':docs,'figure_formats':figures,'archives':archives,'image_aliases':6,
      'external_readonly_pins_retained_not_copied':360,'seconds':time.monotonic()-start,
      'scientific_code_executed':False,'scientific_payloads_parsed':False,'inner_archives_expanded':False,
      'human_author_approval':False,'public_release':False}
if __name__=='__main__':print(json.dumps(main(),indent=2))
