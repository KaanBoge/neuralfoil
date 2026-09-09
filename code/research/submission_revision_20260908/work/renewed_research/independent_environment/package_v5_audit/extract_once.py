"""One explicitly requested private integrity-only extraction, no inner execution."""
from pathlib import Path
import datetime,hashlib,json,time,types,traceback
H=Path(__file__).resolve().parent
PROJECT=next(p for p in H.parents if p.name=='NeuralFoil_Research_Paper')
RESEARCH=PROJECT/'submission_revision_20260908/work/renewed_research'
TOOL=RESEARCH/'package_v4_tools/package_v4.py'
TOOL_SHA='d3ce20b1d959487cc2c4f5c7b35a3d2ca36ab11a3e6f6434d654e664f601f141'
ARCHIVE=PROJECT/'submission_revision_20260908/renewed_manuscript_v8/deliverables/NeuralFoil_Private_Submission_Package_v5.zip'
ARCHIVE_SHA='55125c438bab9f5ca41556c5bf20e8d4d1a1006358b5688fbc018e47a5cb7a82'
MANIFEST_SHA='9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9'
DEST=RESEARCH/'independent_environment/package_v5_fresh_extraction_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def main():
    if DEST.exists() or (H/'EXTRACTION.json').exists() or (H/'EXTRACTION_FAILURE.json').exists():raise FileExistsError('preserve prior attempt')
    start=time.monotonic();begin=datetime.datetime.now(datetime.timezone.utc).isoformat()
    source=TOOL.read_bytes();assert hashlib.sha256(source).hexdigest()==TOOL_SHA
    delivery=ARCHIVE.with_name('NeuralFoil_Private_Submission_Package_v5_DELIVERY.json')
    delivery_sha=sha(delivery)
    module=types.ModuleType('authenticated_unchanged_packager');exec(compile(source,str(TOOL),'exec'),module.__dict__)
    try:
        assert ARCHIVE.stat().st_size==137089855
        result=module.extract(ARCHIVE,ARCHIVE_SHA,MANIFEST_SHA,DEST,max_bytes=512*1024**2)
        assert result['files']==433
        assert sha(TOOL)==TOOL_SHA and sha(ARCHIVE)==ARCHIVE_SHA and sha(delivery)==delivery_sha
        write(H/'EXTRACTION.json',{'status':'PASS_INTEGRITY_ONLY','started_utc':begin,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seconds':time.monotonic()-start,'archive':str(ARCHIVE),'archive_sha256':ARCHIVE_SHA,'manifest_sha256':MANIFEST_SHA,'helper_sha256':TOOL_SHA,'source_sha256':sha(Path(__file__)),'destination':str(DEST),'result':result,'assembly_delivery_sha256_preserved':delivery_sha,'assembly_delivery_status_unchanged':json.loads(delivery.read_text())['status'],'scientific_code_executed':False})
    except BaseException as e:
        write(H/'EXTRACTION_FAILURE.json',{'started_utc':begin,'seconds':time.monotonic()-start,'exception':repr(e),'traceback':traceback.format_exc(),'destination':str(DEST)});raise
if __name__=='__main__':main()
