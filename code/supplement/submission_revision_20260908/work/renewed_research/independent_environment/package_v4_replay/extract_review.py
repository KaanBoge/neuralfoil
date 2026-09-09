"""Independent read-only package replay; outputs exclusively outside payload."""
from pathlib import Path,PurePosixPath
import hashlib,json,subprocess,sys,time,zipfile,stat
HERE=Path(__file__).resolve().parent
ENV=HERE.parent
PROJECT=ENV.parents[3]
EDITION=PROJECT/'submission_revision_20260908/renewed_manuscript_v7'
ARCHIVE=EDITION/'deliverables/NeuralFoil_Private_Submission_Package_v4.zip'
ARCHIVE_SHA='1ae24420b4728dc44c02fb032c277c41263ec2569459c9b20edc2574a4b45454'
MANIFEST_SHA='a14fcee7c9ea63629395d150baa3e1006e841c3de321dc94834c6acde3f95854'
ROOTNAME='NeuralFoil_Private_Submission_Package_v4'
TOOL=PROJECT/'submission_revision_20260908/work/renewed_research/package_v4_tools/package_v4.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):
    with (HERE/name).open('x') as f:json.dump(data,f,indent=2);f.write('\n')
def main():
    assert sha(ARCHIVE)==ARCHIVE_SHA
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.read(ROOTNAME+'/tools/package_v4.py')==TOOL.read_bytes()
        assert hashlib.sha256(z.read(ROOTNAME+'/MANIFEST.json')).hexdigest()==MANIFEST_SHA
    cmd=[sys.executable,'-B',str(TOOL),'extract','--archive',str(ARCHIVE),'--archive-sha256',ARCHIVE_SHA,'--manifest-sha256',MANIFEST_SHA,'--destination',str(HERE/'fresh_extraction')]
    start=time.monotonic();r=subprocess.run(cmd,text=True,capture_output=True)
    save('EXTRACTION.json',{'command':cmd,'exit_code':r.returncode,'seconds':time.monotonic()-start,'stdout':r.stdout,'stderr':r.stderr,'archive_sha256':ARCHIVE_SHA,'manifest_sha256':MANIFEST_SHA,'tool_sha256':sha(TOOL)})
    assert r.returncode==0
    p=HERE/'fresh_extraction'/ROOTNAME
    m=json.loads((p/'MANIFEST.json').read_text())
    q=json.loads((p/'quality/FINAL_TECHNICAL_QA.json').read_text())
    assert sha(p/'quality/FINAL_TECHNICAL_QA.json')=='e96a7dc085cc558b6eb2a4f8dc430fbbbe59aca63a402b652ddc83baddc0de58'
    assert sha(p/'quality/FINAL_AUTHORIZED_CONFIG.json')==q['config_sha256']
    roles={}
    for kind in ['main','supplement']:
        for ext,field in [('pdf','pdf'),('docx','docx'),('md','source' if kind=='main' else 'reading_source')]:
            f=p/f'manuscript/{kind}.{ext}';assert sha(f)==q['documents'][kind]['artifacts'][field]['sha256']
            roles[str(f.relative_to(p))]=sha(f)
    for f in (p/'manuscript/figures').glob('*.png'):assert f.read_bytes()==(p/'figures'/f.name).read_bytes()
    assert len(list((p/'manuscript/figures').glob('*.png')))==5
    assert [len(q['documents'][k]['visual']) for k in ['main','supplement']]==[28,67]
    assert 'NAVIGATION_PLACEHOLDER' not in (p/'manuscript/supplement.md').read_text()
    assert sha(ARCHIVE)==ARCHIVE_SHA
    save('STRUCTURE.json',{'status':'PASS','six_document_roles':roles,'markdown_image_aliases':5,'visual_pages':95,'payload_files':len(m['files']),'no_scientific_code_executed':True})
    print(r.stdout)
if __name__=='__main__':main()
