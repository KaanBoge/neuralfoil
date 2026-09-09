"""Review-only runner until separately pinned actual-request approval is supplied."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,signal,subprocess,sys,time,traceback
import numpy as np
from serving import ROUTES,COHORTS,QUALIFIED,exact
from loader import load
from timing import warm,measured,schedule
H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,value):
    raw=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def check_real(serv,refs):
    # Exact archived feature and prediction checks precede ANY timed requests.
    captured={}
    for route in ROUTES:
        d=serv.request(route,diagnostics=True)
        for c in COHORTS:
            r=refs[c]
            if route.startswith('native_'):
                key='XLARGE_CD' if route==ROUTES[0] else 'BASE_CD'
                np.testing.assert_array_equal(d[c+'/quantized_CD'],r['features'][key])
            else:
                for k,v in r['features'].items():
                    if k not in ['alpha','Re','airfoil']:np.testing.assert_array_equal(d[c+'/'+k],v)
                if route==ROUTES[2]:np.testing.assert_array_equal(d[c+'/CD'],r['original'])
                else:
                    z=r['kl'] if '_kl_' in route else r['native']
                    for field,suffix in [('CD',''),('strength','__strength'),('effective_fraction','__effective_fraction'),('intervened','__intervened')]:
                        np.testing.assert_array_equal(d[c+'/'+field],z[route+suffix])
                    for k in ['core','anchor','gate']:np.testing.assert_array_equal(d[c+'/'+k],r['native'][k])
                    inactive=~d[c+'/gate'];np.testing.assert_array_equal(d[c+'/CD'][inactive],r['features']['BASE_CD'][inactive])
        # Same-shape request outputs captured only AFTER archived checks pass.
        value=serv.request(route)
        if any(not np.isfinite(a).all() for a in value.values()):raise ValueError('nonfinite request')
        captured[route]=value
    return captured
def authorize(args):
    if sha(args.approval)!=args.approval_sha256:raise ValueError('approval hash')
    a=json.loads(Path(args.approval).read_text())
    if a.get('authorized_phase')!='one_fixed_inference_benchmark' or a.get('host_other_scientific_jobs_stopped') is not True:raise ValueError('actual-request/quiet-host approval required')
    if sha(H/'REGISTRY.json')!=a['registry_sha256']:raise ValueError('registry identity')
    r=json.loads((H/'REGISTRY.json').read_text())
    if sys.executable!=r['runtime']:raise ValueError('explicit runtime required')
    for n,h in r['sources'].items():
        if sha(H/n)!=h:raise ValueError('source mutation')
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']):raise ValueError('one thread')
    if Path(args.output).resolve()!=Path(a['output']).resolve():raise ValueError('approved output')
    return a,r
def child(args,r):
    started=time.perf_counter();serv,refs,runtime=load(args.project,r);prepared=time.perf_counter()
    out=Path(args.output)
    if args.phase=='preflight':
        values=check_real(serv,refs)
        flat={route+'::'+k:v for route,d in values.items() for k,v in d.items()}
        with (out/'request_references.npz').open('xb') as f:np.savez_compressed(f,**flat)
        write(out/'PREFLIGHT.json',{'status':'EXACT_ARCHIVED_FIDELITY_PASS','reference_sha256':sha(out/'request_references.npz'),'raw_baseline_scope':'no archived raw external reference; retained source-identical preflight values','runtime':runtime})
        return
    p=json.loads((out/'PREFLIGHT.json').read_text())
    if p['status']!='EXACT_ARCHIVED_FIDELITY_PASS' or sha(out/'request_references.npz')!=p['reference_sha256']:raise ValueError('preflight barrier')
    with np.load(out/'request_references.npz',allow_pickle=False) as z:
        references={route:{k.split('::',1)[1]:z[k] for k in z.files if k.startswith(route+'::')} for route in ROUTES}
    if args.phase=='cold':
        elapsed=measured(serv.request,args.route,references[args.route])
        write(out/('cold_'+args.route+'.json'),{'route':args.route,'first_request_seconds':elapsed,'shared_seven_route_service_setup_seconds':prepared-started,'cold_process_not_OS_cache':True,'rows':497})
    elif args.phase=='warm':
        def emit(v):write(out/(f"warm_{v['repeat']}_{v['route']}.json"),v)
        warm(serv.request,references,emit)
def supervise(args,r):
    out=Path(args.output)
    if out.exists():raise FileExistsError('output collision')
    out.mkdir();start=time.monotonic()
    write(out/'ATTEMPT.json',{'started_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'approval_sha256':args.approval_sha256,'registry_sha256':sha(H/'REGISTRY.json'),'schedule':schedule(),'load_average':os.getloadavg(),'platform':platform.platform(),'cpu':platform.processor(),'rss_method':'macOS ps -o rss= -p direct child; KiB converted to bytes; sampled at 0.1 seconds','cold_setup_scope':'shared seven-route service authenticates and loads all models; not standalone baseline-only cold-start cost'})
    jobs=[('preflight',None)]+[('cold',route) for route in ROUTES]+[('warm',None)]
    try:
        for phase,route in jobs:
            name=phase+('_'+route if route else '')
            command=[sys.executable,str(H/'runner.py'),'--project',args.project,'--approval',args.approval,'--approval-sha256',args.approval_sha256,'--output',args.output,'--phase',phase]
            if route:command+=['--route',route]
            before=time.monotonic();peak=0
            with (out/(name+'.stdout')).open('x') as so,(out/(name+'.stderr')).open('x') as se:
                proc=subprocess.Popen(command,stdout=so,stderr=se)
                reason=None
                while proc.poll() is None:
                    raw=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True).stdout.strip()
                    if raw:peak=max(peak,int(raw)*1024)
                    if peak>r['max_rss_bytes']:reason='RSS stop threshold'
                    if time.monotonic()-start>r['max_seconds']:reason='total wall stop threshold'
                    if sum(p.stat().st_size for p in out.iterdir() if p.is_file())>1024**3:reason='output size stop threshold'
                    if reason:proc.terminate();proc.wait(timeout=10);break
                    time.sleep(.1)
            write(out/(name+'_process.json'),{'exit_code':proc.returncode,'elapsed_seconds':time.monotonic()-before,'peak_sampled_RSS_bytes':peak,'stop_reason':reason})
            if proc.returncode or reason:raise RuntimeError(name+' failed; no retry')
        authorize(args)
        write(out/'COMPLETE.json',{'status':'COMPLETE_REQUIRES_INDEPENDENT_REVIEW','seconds':time.monotonic()-start,'warm_records':49,'cold_records':7,'new_fits':0,'load_average_end':os.getloadavg(),'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    except BaseException as e:
        write(out/'FAILURE.json',{'exception':repr(e),'traceback':traceback.format_exc(),'seconds':time.monotonic()-start});raise
def main():
    p=argparse.ArgumentParser()
    for k in ['project','approval','approval-sha256','output']:p.add_argument('--'+k,required=True)
    p.add_argument('--phase',choices=['parent','preflight','cold','warm'],default='parent');p.add_argument('--route',choices=ROUTES)
    args=p.parse_args();a,r=authorize(args)
    def timeout(*unused):raise TimeoutError('request budget')
    signal.signal(signal.SIGALRM,timeout)
    if args.phase=='parent':supervise(args,r)
    else:
        # Per-request guard is installed around every request, not whole warm run.
        original=ServingRequest=__import__('serving').Serving.request
        def guarded(self,*x,**kw):
            signal.alarm(r['max_request_seconds'])
            try:return original(self,*x,**kw)
            finally:signal.alarm(0)
        __import__('serving').Serving.request=guarded
        child(args,r)
if __name__=='__main__':main()
