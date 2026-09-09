"""Task-local pinned-wheel provisioning; never inherit site-packages."""
import json, os, pathlib, subprocess, sys, time, urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent
BASE={'fit':'/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/.venv/bin/python','forward':'/opt/anaconda3/bin/python'}
REQ={'fit':['numpy==2.3.5','scipy==1.16.1','scikit-learn==1.7.1','pandas==2.2.3','joblib==1.6.0','threadpoolctl==3.6.0','python-dateutil==2.9.0.post0','pytz==2026.3.post1','tzdata==2026.3','six==1.17.0'], 'forward':['numpy==2.3.5','aerosandbox==4.2.10','neuralfoil==0.3.3','casadi==3.7.2']}
ENV={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','PIP_'))}
ENV.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PIP_CONFIG_FILE=os.devnull,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PIP_CACHE_DIR=str(ROOT/'pip_cache'))
REQ['forward'] += ['scipy==1.16.3','pandas==2.3.3','matplotlib==3.11.1','dill==0.4.0','sortedcontainers==2.4.0','seaborn==0.13.2','contourpy==1.3.3','cycler==0.11.0','fonttools==4.60.1','kiwisolver==1.4.9','packaging==25.0','pillow==12.0.0','pyparsing==3.2.5','python-dateutil==2.9.0.post0','six==1.17.0','tqdm==4.67.1']
def execute(label,cmd):
    t=time.monotonic()
    with (ROOT/(label+'.log')).open('x') as f:p=subprocess.run(list(map(str,cmd)),env=ENV,stdout=f,stderr=subprocess.STDOUT)
    record={'command':list(map(str,cmd)),'returncode':p.returncode,'seconds':time.monotonic()-t}
    with (ROOT/(label+'.json')).open('x') as f:json.dump(record,f,indent=2)
    print(label,record,flush=True)
    if p.returncode:raise RuntimeError(label+' failed; preserve log')
if __name__=='__main__':
    kind,stage=sys.argv[1:]
    dest=ROOT/('venv_'+kind); py=dest/'bin/python'
    if stage in ('resolve','resolve_network','resolve_pinned'):
        if stage=='resolve':
            if dest.exists():raise FileExistsError(dest)
            execute(kind+'_create',[BASE[kind],'-I','-m','venv',dest])
        report_name=kind+('_pinned_resolution.json' if stage=='resolve_pinned' else '_resolution.json')
        execute(kind+'_'+stage,[py,'-I','-m','pip','install','--dry-run','--ignore-installed','--only-binary=:all:','--index-url','https://pypi.org/simple','--report',ROOT/report_name,*REQ[kind]])
    elif stage=='install':
        report=json.loads((ROOT/(kind+('_pinned_resolution.json' if kind=='forward' else '_resolution.json'))).read_text())
        for item in report['install']:
            url=item['download_info']['url']; assert urllib.parse.urlparse(url).hostname=='files.pythonhosted.org',url
            assert url.endswith('.whl'),url
            assert item['download_info']['archive_info']['hashes']['sha256']
        # Install exact resolved wheel URLs, not a second unconstrained resolution.
        execute(kind+'_install',[py,'-I','-m','pip','install','--no-deps','--only-binary=:all:','--report',ROOT/(kind+'_installation.json'),*[x['download_info']['url']+'#sha256='+x['download_info']['archive_info']['hashes']['sha256'] for x in report['install']]])
        execute(kind+'_check',[py,'-I','-m','pip','check'])
    else:raise ValueError(stage)
