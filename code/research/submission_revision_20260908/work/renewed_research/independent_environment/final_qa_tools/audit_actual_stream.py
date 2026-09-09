"""Independent opaque file hashing and saved receipt audit; no scientific parsing."""
import hashlib,json,time
from pathlib import Path
P=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
B=P/'submission_revision_20260908/work/renewed_research/uncertainty_review/package_v6_plan'
def digest(p):
    h=hashlib.sha256(); n=0
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b);n+=len(b)
    return h.hexdigest(),n
def main():
    start=time.monotonic();pins={}
    def auth(p,h=None):
        v,n=digest(p)
        if h is not None:assert v==h,str(p)
        pins[str(p)]=v
        return n
    def meta(p,h=None):
        auth(p,h);return json.loads(p.read_bytes())
    ca=meta(B/'ROOT_CREATE_APPROVAL_v1.json','a7c7725260433cee7e452fe8eda572a47e6f4f5ba154717c0d9bf6df41cd03ad')
    va=meta(B/'ROOT_VERIFY_APPROVAL_v1.json','8c1592cd67f6ad8c9c972e73d9c1b4b8b336ce468bd7314f97dfa0c42aae2577')
    cr=meta(B/'create_attempt_1/COMPLETE.json','b4f573da18c398595e502440be0754309dd8aaa93cc57bcfd706679e4296c45a')
    vr=meta(B/'extract_attempt_1/COMPLETE.json')
    s=meta(P/ca['selection'],ca['selection_sha256'])
    for a,r,phase in [(ca,cr,'CREATE'),(va,vr,'VERIFY_EXTRACT')]:
        assert a['execution_authorized'] is True and a['phase']==r['phase']==phase
        assert a['workers']==1 and a['max_seconds']==900 and 0<r['seconds']<900
        assert a['max_expanded_bytes']==2415919104 and a['max_archive_bytes']==251658240
        assert r['selection_sha256']==a['selection_sha256']==ca['selection_sha256']
        assert r['source_pins']==a['source_pins']==ca['source_pins']
        assert r['scientific_execution'] is False
        for n,h in a['source_pins'].items():auth(P/n,h)
    assert cr['approval_sha256']==pins[str(B/'ROOT_CREATE_APPROVAL_v1.json')]
    assert vr['approval_sha256']==pins[str(B/'ROOT_VERIFY_APPROVAL_v1.json')]
    assert cr['status']=='CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING'
    assert vr['status']=='VERIFIED_STREAMED_EVIDENCE' and vr['portable_pipeline_replayed'] is False
    assert va['writer_receipt_sha256']==vr['writer_receipt_sha256']==pins[str(B/'create_attempt_1/COMPLETE.json')]
    assert va['writer_approval_sha256']==cr['approval_sha256']
    assert P/va['writer_receipt']==B/'create_attempt_1/COMPLETE.json'
    assert P/va['writer_approval']==B/'ROOT_CREATE_APPROVAL_v1.json'
    assert P/ca['output']==B/'create_attempt_1' and P/va['output']==B/'extract_attempt_1'
    archive=P/va['archive']
    assert va['archive_sha256']==cr['archive_sha256']==vr['archive_sha256']=='2d5bc9bfe0a614ee4fb53ec1bce6120eeda8304e5df6d2d85aedfc8501ac051b'
    size=auth(archive,va['archive_sha256'])
    assert size==cr['archive_bytes']==vr['archive_bytes']==127279242
    root=B/'extract_attempt_1/payload'
    m=meta(root/'MANIFEST.json','54cea9fac407bef51a29734cb4b657c0ea9f3ef104a55e41b69949a94b95bb87')
    assert m['files']=={r['target']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in s['files']}
    assert m['claim']==s['claim']=='SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE'
    observed={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert observed==set(m['files'])|{'MANIFEST.json'}
    total=0
    for n,r in m['files'].items():
        p=root/n
        assert not any(x.is_symlink() for x in (p,*p.parents))
        h,count=digest(p)
        assert (h,count)==(r['sha256'],r['bytes']),n
        total+=count
    assert len(m['files'])==cr['files']==vr['files']==1644
    assert total==cr['payload_bytes']==vr['verified_payload_bytes']==934080471
    assert total+(root/'MANIFEST.json').stat().st_size==cr['expanded_bytes']==934503969
    assert vr['disk_files_reopened']==1645 and cr['compressed_highwater']==size
    assert not (B/'create_attempt_1/FAILURE.json').exists() and not (B/'extract_attempt_1/FAILURE.json').exists()
    for n,h in list(pins.items()):assert digest(Path(n))[0]==h
    return {'status':'PASS_INDEPENDENT_OPAQUE_INTEGRITY_AUDIT','source_and_receipt_pins':pins,
      'selected_payload_files':1644,'fresh_disk_files':1645,'payload_bytes':total,'manifest_bytes':423498,
      'expanded_bytes':934503969,'archive_bytes':size,'create_seconds_recorded':cr['seconds'],
      'verify_seconds_recorded':vr['seconds'],'audit_seconds':time.monotonic()-start,
      'scientific_payloads_parsed':False,'phases_rerun':False,'archive_decompression_rerun':False,
      'actual_disk_file_hashes_verified':True,'portable_pipeline_replayed':False}
if __name__=='__main__':print(json.dumps(main(),indent=2))
