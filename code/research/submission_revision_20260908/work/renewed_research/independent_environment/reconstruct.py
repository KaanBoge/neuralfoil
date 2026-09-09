"""Witnessed clean-venv reproduction; frozen source is never patched."""
import hashlib,importlib.util,json,os,pathlib,stat,subprocess,sys,time,zipfile
from provision import ROOT,ENV,execute
REV=ROOT.parents[2]
PACKAGE=REV/'deliverables/NeuralFoil_Private_Submission_Package_v2'
WRAPPER=PACKAGE/'reproduction/connected/reviewer.py'
PY=ROOT/'venv_fit/bin/python'; FWD=ROOT/'venv_forward/bin/python'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(name,data):
    with (ROOT/name).open('x') as f:json.dump(data,f,indent=2)
def extract(p,dest,digest,prefix,manifest):
    assert sha(p)==digest
    assert not dest.exists()
    with zipfile.ZipFile(p) as z:
        names=z.namelist();assert len(names)==len(set(names))
        mname=(prefix+'/' if prefix else '')+manifest
        m=json.loads(z.read(mname));files=m['files']; covered={mname}
        for name,h in files.items():
            full=(prefix+'/' if prefix else '')+name
            assert hashlib.sha256(z.read(full)).hexdigest()==h
            covered.add(full)
        assert covered==set(names)
        for info in z.infolist():
            name=pathlib.PurePosixPath(info.filename)
            assert not name.is_absolute() and '..' not in name.parts and not stat.S_ISLNK(info.external_attr>>16)
        dest.mkdir()
        z.extractall(dest)
    return {'archive_sha256':digest,'files':len(files),'manifest_sha256':sha(dest/mname)}
def isolation(kind,py):
    code='''import sys,site,json,importlib.metadata as m,pathlib,platform
r=pathlib.Path(sys.prefix).resolve()
assert sys.prefix!=sys.base_prefix
assert site.ENABLE_USER_SITE is False
assert "include-system-site-packages = false" in (r/"pyvenv.cfg").read_text()
assert all(str(r) in p for p in sys.path if "site-packages" in p)
d=[{"name":x.metadata["Name"],"version":x.version,"location":str(x.locate_file(""))} for x in m.distributions()]
assert all(pathlib.Path(x["location"]).resolve().is_relative_to(r) for x in d)
print(json.dumps({"python":sys.version,"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"platform":platform.platform(),"machine":platform.machine(),"sys_path":sys.path,"user_site_enabled":site.ENABLE_USER_SITE,"pyvenv_cfg":(r/"pyvenv.cfg").read_text(),"distributions":d},indent=2))'''
    execute(kind+'_isolation',[py,'-I','-c',code])
if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='light':
        isolation('fit',PY)
        execute('outer_integrity',[PY,'-B',PACKAGE/'verify_submission_package.py','--manifest-sha256','228d4473664f7f98d85d0dae9ecd01bea7e3c63ce82600b87ff8a3644e51fe56'])
        execute('wrapper_integrity',[PY,'-B',WRAPPER,'verify'])
        bound=PACKAGE/'reproduction/bounds/bounds_private.zip'
        reference=PACKAGE/'reproduction/references/reference_reproduction_private.zip'
        manifests={'bounds':extract(bound,ROOT/'bounds_extraction','4d3aad28685c65f8b76a5eccb50e10d6209c77a568898844ae270d6c6837ff30','','manifest.json'),
          'references':extract(reference,ROOT/'reference_extraction','5ed12092e3d4f8543791ff750d35f61e6172657d0fc1b1343f6240aaa73fb3bd','reference_reproduction','release_manifest.json')}
        dump('extraction_witness.json',manifests)
        b=ROOT/'bounds_extraction';r=ROOT/'reference_extraction/reference_reproduction'
        execute('bounds_tests',[PY,'-B','-m','unittest','discover','-s',b,'-v'])
        execute('bounds_replay',[PY,'-B',b/'check.py','--manifest-sha256','210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea'])
        execute('reference_tests',[PY,'-B','-m','unittest','discover','-s',r,'-p','test_replay.py','-v'])
        execute('reference_saved_replay',[PY,'-B',r/'verify_results.py'])
    elif stage=='connected':
        isolation('forward',FWD)
        execute('wrapper_tests',[PY,'-B','-m','unittest','discover','-s',WRAPPER.parent,'-p','test_reviewer.py','-v'])
        dump('pre_fit_witness.json',{'plan_sha256':sha(ROOT/'PLAN.md'),'driver_sha256':sha(__file__),'wrapper_sha256':sha(WRAPPER),'fit_isolation_sha256':sha(ROOT/'fit_isolation.log'),'forward_isolation_sha256':sha(ROOT/'forward_isolation.log'),'scope':'Fresh third-party installations, shared interpreter binaries/macOS/hardware. Frozen original wrapper descriptive flags retained unchanged.'})
        execute('connected_reconstruction',[PY,'-B',WRAPPER,'reproduce','--forward-python',FWD,'--fit-python',PY,'--output',ROOT/'connected_attempt_1'])
    elif stage=='reference_fit':
        execute('reference_reconstruction',[PY,'-B',ROOT/'reference_extraction/reference_reproduction/replay.py','run','--output',ROOT/'reference_attempt_1'])
    elif stage=='standalone_fit':
        execute('standalone_correction_tests',[PY,'-B','-m','unittest','discover','-s',ROOT/'connected_attempt_1/private_reproduction','-v'])
        execute('standalone_correction_reconstruction',[PY,'-B',ROOT/'connected_attempt_1/private_reproduction/reproduce.py'])
    else:raise ValueError(stage)
