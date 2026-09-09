"""Finite archived-component synthetic tests and saved-output verification only."""
from pathlib import Path,PurePosixPath
import ast,hashlib,json,os,stat,subprocess,time,zipfile
from extract_review import HERE,ENV,ROOTNAME,ARCHIVE,ARCHIVE_SHA,sha,save
PACKAGE=HERE/'fresh_extraction'/ROOTNAME
FIT=ENV/'venv_fit/bin/python'
FORWARD=ENV/'conda_forward/bin/python'
ROOTS={'feature':'feature_reproduction','correction':'private_reproduction','bounds':'','references':'reference_reproduction','incremental_harm':'incremental_harm_private','label_sensitivity':'portable_sensitivity'}
TESTS={'feature':['test_feature_math.py'],'correction':None,'bounds':['test_check'],'references':['test_replay.py'],'incremental_harm':['test_incremental_harm.py','test_integrity.py'],'label_sensitivity':['test_sensitivity','test_portable']}
def main():
    guide=(PACKAGE/'REPLAY_GUIDE.md').read_text()
    code=guide.split("python3 -B - <<'PY'\n",1)[1].split('\nPY\n',1)[0]
    tree=ast.parse(code)
    archives=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='archives' for t in n.targets)))
    assert set(archives)==set(ROOTS)
    records=[];inner=[]
    process_env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    def run(name,cmd,cwd):
        start=time.monotonic()
        try:
            r=subprocess.run([str(x) for x in cmd],cwd=cwd,env=process_env,text=True,capture_output=True,timeout=180)
            row={'name':name,'command':[str(x) for x in cmd],'cwd':str(cwd),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'seconds':time.monotonic()-start}
        except subprocess.TimeoutExpired as e:
            row={'name':name,'exit_code':None,'failure':'timeout180s','seconds':time.monotonic()-start}
        records.append(row);save(name+'.json',row);print(name,row['exit_code'],flush=True)
    run('outer_package_tests',[FIT,'-B','-m','unittest','-q','test_package_v4.py'],PACKAGE/'tools')
    for name,(relative,expected) in archives.items():
        archive=PACKAGE/'reproduction'/relative
        assert sha(archive)==expected
        dest=HERE/'inner_extractions'/name
        assert not dest.exists()
        with zipfile.ZipFile(archive) as z:
            infos=z.infolist();names=[x.filename.rstrip('/') for x in infos]
            assert len(names)==len(set(n.casefold() for n in names))
            assert sum(x.file_size for x in infos)<512*1024*1024
            for item in infos:
                parts=PurePosixPath(item.filename)
                assert not parts.is_absolute() and '..' not in parts.parts and '\\' not in item.filename
                assert stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG,stat.S_IFDIR)
                assert not any('/'.join(parts.parts[:i]) in names for i in range(1,len(parts.parts)))
            if ROOTS[name]:assert {n.split('/')[0] for n in names}=={ROOTS[name]}
            dest.mkdir(parents=True)
            z.extractall(dest)
        cwd=dest/ROOTS[name]
        inner.append({'id':name,'archive_sha256':expected,'root':ROOTS[name],'files':len(infos)})
        cmd=[FORWARD if name=='feature' else FIT,'-B','-m','unittest']
        cmd+=['discover','-q'] if TESTS[name] is None else ['-q',*TESTS[name]]
        run(name+'_tests',cmd,cwd)
        if name=='references':run('reference_saved_outputs',[FIT,'-B','verify_results.py'],cwd)
        if name=='bounds':run('bounds_certificate',[FIT,'-B','check.py','--manifest-sha256','210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea'],cwd)
    assert sha(ARCHIVE)==ARCHIVE_SHA
    save('NO_FIT_CHECKS.json',{'status':'PASS' if all(r['exit_code']==0 for r in records) else 'FAILURES_RETAINED','records':records,'archives':inner,'new_project_model_fits':0,'scope':'Synthetic unit tests and saved-output/certificate replay only; no full scientific refits or new installs'})
if __name__=='__main__':main()
