"""Offline authenticated distribution installation, not installed-tree cloning."""
import hashlib,json,pathlib,shutil,sys
from provision import ROOT,ENV,execute
from reconstruct import PACKAGE,WRAPPER,extract,dump,sha
PREFIX=ROOT/'conda_forward';PY=PREFIX/'bin/python'
ENV.update(CONDA_PKGS_DIRS=str(ROOT/'conda_package_cache'),CONDA_ENVS_PATH=str(ROOT/'conda_env_registry'),CONDA_REGISTER_ENVS='false',CONDA_NO_PLUGINS='true',CONDA_OFFLINE='true',CONDA_SOLVER='classic',CONDA_AUTO_UPDATE_CONDA='false',CONDA_NOTIFY_OUTDATED_CONDA='false',CONDA_REPORT_ERRORS='false')
if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='provision':
        assert not PREFIX.exists()
        meta=pathlib.Path('/opt/anaconda3/conda-meta')
        ds={j['name']:(p,j) for p in meta.glob('*.json') for j in [json.loads(p.read_text())]}
        seen=set();todo=['python','numpy','numpy-base','scipy','pip']
        while todo:
            name=todo.pop()
            if name in seen or name.startswith('__'):continue
            seen.add(name);j=ds[name][1];todo.extend(d.split()[0] for d in j['depends'])
        records=[];files=[];cache=ROOT/'conda_archives';cache.mkdir()
        for name in sorted(seen):
            source,j=ds[name];p=pathlib.Path('/opt/anaconda3/pkgs')/j['fn']
            assert j['url'].startswith('https://repo.anaconda.com/')
            assert sha(p)==j['sha256']
            target=cache/p.name;assert not target.exists();shutil.copyfile(p,target);assert sha(target)==j['sha256']
            files.append(target);records.append({'name':name,'version':j['version'],'build':j['build'],'filename':p.name,'bytes':p.stat().st_size,'sha256':j['sha256'],'original_official_url':j['url'],'metadata_sha256':sha(source)})
        assert len(records)==27 and sum(r['bytes'] for r in records)==61368828
        dump('conda_closure.json',{'archives':records,'plan_sha256':sha(ROOT/'MATCHED_BUILD_PLAN.md'),'driver_sha256':sha(__file__),'register_envs':False,'copy_not_hardlink':True})
        cmd=['/opt/anaconda3/bin/python','-I','-m','conda','create','--offline','--copy','--no-default-packages','--no-shortcuts','--yes','--prefix',PREFIX,*files]
        execute('conda_dry_run',[*cmd,'--dry-run','--json'])
        execute('conda_create',cmd)
    elif stage=='wheels':
        r=json.loads((ROOT/'forward_pinned_resolution.json').read_text())
        items=[i for i in r['install'] if i['metadata']['name'].lower() not in ['numpy','scipy']]
        execute('conda_forward_wheels',[PY,'-I','-m','pip','install','--no-deps','--report',ROOT/'conda_wheel_installation.json',*[i['download_info']['url']+'#sha256='+i['download_info']['archive_info']['hashes']['sha256'] for i in items]])
        execute('conda_forward_check',[PY,'-I','-m','pip','check'])
    elif stage=='replay':
        code='''import sys,site,pathlib,json,importlib.metadata as m,numpy as np
r=pathlib.Path(sys.prefix).resolve();assert str(r).endswith("/conda_forward")
assert site.ENABLE_USER_SITE is False
assert all(str(r) in p for p in sys.path if "site-packages" in p)
d=[{"name":x.metadata["Name"],"version":x.version,"location":str(x.locate_file(""))} for x in m.distributions()]
assert all(pathlib.Path(x["location"]).resolve().is_relative_to(r) for x in d)
print(json.dumps({"python":sys.version,"prefix":sys.prefix,"sys_path":sys.path,"user_site_enabled":site.ENABLE_USER_SITE,"distributions":d},indent=2));np.show_config()'''
        # -I disables user site even for an independently installed full prefix.
        execute('conda_isolation',[PY,'-I','-c',code])
        p=PACKAGE/'reproduction/connected/archives/feature_reproduction_private.zip'
        witness=extract(p,ROOT/'matched_feature_extraction','eeaa0435dc140d8bf89a76c29fdca188c519aa65dba044d52b190ade3df016b5','feature_reproduction','release_manifest.json')
        dump('matched_feature_extraction.json',witness)
        f=ROOT/'matched_feature_extraction/feature_reproduction'
        execute('matched_feature_tests',[PY,'-B','-m','unittest','discover','-s',f,'-v'])
        ENV['MPLCONFIGDIR']=str(ROOT/'matched_mpl')
        execute('matched_feature_generation',[PY,'-B',f/'regenerate_portable.py','--output',ROOT/'matched_feature_results'])
        execute('matched_feature_bridge',[PY,'-B',WRAPPER,'verify','--feature-results',ROOT/'matched_feature_results','--report',ROOT/'matched_bridge.json'])
    else:raise ValueError(stage)
