"""Manufactured reserved-manifest and late-symlink probes; no real archives."""
import hashlib,importlib.util,json,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[5]
SOURCE=PROJECT/'submission_revision_20260908/renewed_manuscript_v9/work/package_documents/verify_saved_evidence.py'
EXPECTED='0a92061077bed894ddc942bf8668b67318151d2ef6bf18279958a2786cedbb9b'
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(SOURCE.read_bytes())==EXPECTED
spec=importlib.util.spec_from_file_location('reviewed_checker',SOURCE)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
findings=[]
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();archive=root/'synthetic.zip'
    m=dict(schema='v9-saved-evidence-1',selection_sha256='a'*64,claim='SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE',
           files={'MANIFEST.json':{'bytes':0,'sha256':'0'*64}})
    for _ in range(10):
        raw=json.dumps(m).encode()
        if m['files']['MANIFEST.json']['bytes']==len(raw):break
        m['files']['MANIFEST.json']['bytes']=len(raw)
    assert m['files']['MANIFEST.json']['bytes']==len(raw)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('MANIFEST.json',raw)
    result=v.verify(archive,sha(archive.read_bytes()),sha(raw))
    findings.append(dict(case='reserved_manifest_wrong_declared_hash',result=result,
                         declared_hash='0'*64,actual_hash=sha(raw),unexpected_acceptance=True))
    m['files']={'a':{'bytes':1,'sha256':sha(b'x')}};raw=json.dumps(m).encode()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('MANIFEST.json',raw);z.writestr('a',b'x')
    archive_hash=sha(archive.read_bytes());same=root/'identical.zip';same.write_bytes(archive.read_bytes())
    original=v.stream_hash
    def substitute(reader,limit,check):
        result=original(reader,limit,check)
        if type(reader).__name__=='ZipExtFile' and getattr(reader,'name','')=='a':
            archive.unlink();archive.symlink_to(same)
        return result
    with patch.object(v,'stream_hash',substitute):result=v.verify(archive,archive_hash,sha(raw))
    assert archive.is_symlink()
    findings.append(dict(case='archive_same_bytes_symlink_after_initial_admission',result=result,unexpected_acceptance=True))
out=dict(source_sha256=EXPECTED,scope='Synthetic only, no actual archive',findings=findings)
with (HERE/'ADVERSARIAL_FINDINGS.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out))
