"""Strict source bootstrap and one authorized benchmark; no implicit permission."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,resource,signal,subprocess,sys,time,traceback,types
H=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(path):
    p=Path(path)
    if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink')
    return p.read_bytes()
def write(path,value):
    b=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    with Path(path).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def accept_output(path,accepted,expected=None):
    h=sha(raw(path))
    if expected is not None and h!=expected:raise ValueError('expected output identity')
    if path.name in accepted and accepted[path.name]!=h:raise ValueError('first-accepted output changed')
    accepted[path.name]=h
def authorize(args):
    ab=raw(args.approval)
    if sha(ab)!=args.approval_sha256:raise ValueError('approval identity')
    a=json.loads(ab)
    required={'authorized_phase','registry_sha256','host_other_scientific_jobs_stopped','output','runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','routes','schedule','cold_repeats','warmups','warm_repeats','workers','reference_contract'}
    if set(a)!=required or a['authorized_phase']!='one_fixed_inference_benchmark_v5' or a['host_other_scientific_jobs_stopped'] is not True:raise ValueError('approval schema/scope')
    rb=raw(H/'REGISTRY_v5.json')
    if sha(rb)!=a['registry_sha256']:raise ValueError('registry identity')
    r=json.loads(rb)
    for k in ['runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','routes','schedule','cold_repeats','warmups','warm_repeats','workers','reference_contract']:
        if type(a[k]) is not type(r[k]) or a[k]!=r[k]:raise ValueError('approval contract '+k)
    if sys.executable!=r['runtime'] or platform.system()!='Darwin':raise ValueError('runtime/platform')
    if Path(args.output).resolve()!=Path(a['output']).resolve():raise ValueError('output scope')
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']):raise ValueError('thread scope')
    sources={n:raw(H/n) for n in r['sources']}
    for n,b in sources.items():
        if sha(b)!=r['sources'][n]:raise ValueError('source changed '+n)
    return a,r,sources,ab,rb
def execute_sources(sources):
    saved={};events=[]
    try:
        for name,file in [('provenance_v2','provenance_v2.py'),('serving','serving.py'),('timing','timing.py'),('oracle_v5','oracle_v5.py'),('loader_v5','loader_v5.py'),('measurement_v5','measurement_v5.py'),('watchdog_v3','watchdog_v3.py')]:
            saved[name]=sys.modules.get(name);m=types.ModuleType(name);m.__file__=str(H/file);sys.modules[name]=m
            exec(compile(sources[file],str(H/file),'exec'),m.__dict__)
            events.append({'operation':'source execution','file':str(H/file),'sha256':sha(sources[file])})
    except BaseException:restore(saved);raise
    return saved,events
def restore(saved):
    for name,m in saved.items():
        if m is None:sys.modules.pop(name,None)
        else:sys.modules[name]=m
def finish_bootstrap(args,a,r,sources,ab,rb,events):
    if raw(args.approval)!=ab or raw(H/'REGISTRY_v5.json')!=rb:raise ValueError('approval/registry changed')
    for n,b in sources.items():
        if raw(H/n)!=b:raise ValueError('source changed '+n)
    events.extend([{'operation':'finish source authentication','file':str(H/n),'sha256':sha(b)} for n,b in sources.items()])
    events.extend([{'operation':'finish approval authentication','file':args.approval,'sha256':sha(ab)},{'operation':'finish registry authentication','file':str(H/'REGISTRY_v5.json'),'sha256':sha(rb)}])
def child(args,a,r,sources,ab,rb,events):
    import numpy as np
    from loader_v5 import load,finish
    from measurement_v5 import preflight,measured,warm
    out=Path(args.output);identity=args.phase+('_'+args.route if args.route else '')
    outputs={};access=None;start=time.perf_counter()
    try:
        predecessor=None
        if args.phase!='preflight':
            p=out/'preflight_COMPLETE.json';b=raw(p)
            if sha(b)!=args.predecessor_sha256:raise ValueError('predecessor identity')
            predecessor=json.loads(b)
            if predecessor['status']!='PASS' or predecessor['approval_sha256']!=sha(ab) or predecessor['registry_sha256']!=sha(rb):raise ValueError('predecessor scope')
            events.append({'operation':'JSON parse','file':str(p),'sha256':sha(b)})
        route=args.route if args.phase=='cold' else None
        from provenance_v2 import Access
        access=Access(args.project,r['scopes']['all' if route is None else route])
        serv,refs,runtime,access,runtime_pins=load(args.project,r,route=route,with_references=args.phase=='preflight',access=access)
        prepared=time.perf_counter()
        original=serv.request
        def guarded(*x,**kw):
            signal.alarm(r['max_request_seconds'])
            try:return original(*x,**kw)
            finally:signal.alarm(0)
        serv.request=guarded
        if args.phase=='preflight':
            values,archive_inventory=preflight(serv,refs)
            p=out/'ARCHIVE_COMPARISONS.json';write(p,archive_inventory);outputs[p.name]=sha(raw(p))
            for reference_route,v in values.items():
                p=out/('reference_'+reference_route+'.npz')
                with p.open('xb') as f:np.savez_compressed(f,**v)
                outputs[p.name]=sha(raw(p))
        else:
            routes=[route] if route else r['routes'];references={}
            for label in routes:
                p=out/('reference_'+label+'.npz');b=raw(p)
                if sha(b)!=predecessor['outputs'][p.name]:raise ValueError('predecessor output identity')
                events.append({'operation':'file read','file':str(p),'sha256':sha(b)})
                import io
                with np.load(io.BytesIO(b),allow_pickle=False) as z:
                    references[label]={}
                    for k in z.files:
                        v=z[k]
                        if v.dtype.hasobject:raise ValueError('reference object')
                        references[label][k]=v
                        events.append({'operation':'NPZ member materialization','file':str(p),'sha256':sha(b),'member':k,'shape':list(v.shape),'dtype':str(v.dtype)})
                outputs[p.name]=sha(b)
            if args.phase=='cold':
                elapsed=measured(serv,route,references[route])
                p=out/('cold_'+route+'.json');write(p,{'route':route,'request_seconds':elapsed,'route_specific_setup_seconds':prepared-start,'cold_process_not_OS_cache':True,'rows':497});outputs[p.name]=sha(raw(p))
            else:
                def emit(v):
                    p=out/(f"warm_{v['repeat']}_{v['route']}.json");write(p,v);outputs[p.name]=sha(raw(p))
                counts=warm(serv,references,emit)
                p=out/'WARM_COUNTS.json';write(p,counts);outputs[p.name]=sha(raw(p))
        finish(access,runtime_pins)
        if predecessor:
            if sha(raw(out/'preflight_COMPLETE.json'))!=args.predecessor_sha256:raise ValueError('predecessor changed')
        for n,h in outputs.items():
            if sha(raw(out/n))!=h:raise ValueError('output/reference changed')
        finish_bootstrap(args,a,r,sources,ab,rb,events)
        record={'reference_contract':r['reference_contract'],'status':'PASS','phase':args.phase,'route':route,'approval_sha256':sha(ab),'registry_sha256':sha(rb),'predecessor_sha256':args.predecessor_sha256,'outputs':outputs,'events':events+access.events,'runtime':runtime,'elapsed_seconds':time.perf_counter()-start,'self_ru_maxrss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'ru_maxrss_units':'bytes on explicitly required macOS'}
        write(out/(identity+'_COMPLETE.json'),record)
    except BaseException as e:
        write(out/(identity+'_FAILURE.json'),{'exception':repr(e),'traceback':traceback.format_exc(),'events':events+(access.events if access else []),'elapsed_seconds':time.perf_counter()-start});raise
def parent(args,a,r,sources,ab,rb,events):
    from watchdog_v3 import monitor,budget
    out=Path(args.output)
    if out.exists():raise FileExistsError('output collision')
    if not out.parent.is_dir():raise ValueError('existing output parent required')
    out.mkdir();start=time.monotonic();processes=[];predecessor=None;accepted={}
    size=lambda:sum(p.stat().st_size for p in out.iterdir() if p.is_file())
    def check_budget():budget(start,r['max_seconds'],size,r['max_output_bytes'])
    def accept(path,expected=None):
        accept_output(path,accepted,expected)
    write(out/'ATTEMPT.json',{'approval_sha256':sha(ab),'registry_sha256':sha(rb),'started_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'load_average':os.getloadavg(),'platform':platform.platform(),'schedule':r['schedule'],'rss_method':'direct-child macOS ps KiB at100ms plus child self ru_maxrss bytes; fail closed unavailable monitor','host_quiet_assertion':a['host_other_scientific_jobs_stopped']})
    accept(out/'ATTEMPT.json')
    try:
        for phase,route in [('preflight',None)]+[('cold',x) for x in r['routes']]+[('warm',None)]:
            check_budget()
            identity=phase+('_'+route if route else '')
            command=[sys.executable,str(H/'runner_v5.py'),'--project',args.project,'--approval',args.approval,'--approval-sha256',args.approval_sha256,'--output',args.output,'--phase',phase]
            if route:command+=['--route',route]
            if predecessor:command+=['--predecessor-sha256',predecessor]
            before=time.monotonic()
            with (out/(identity+'.stdout')).open('x') as so,(out/(identity+'.stderr')).open('x') as se:
                proc=subprocess.Popen(command,stdout=so,stderr=se)
                result=monitor(proc,start,r['max_seconds'],r['max_rss_bytes'],size,r['max_output_bytes'])
            result['elapsed_seconds']=time.monotonic()-before;result['command']=command
            write(out/(identity+'_PROCESS.json'),result);processes.append(result)
            if result['failure']:raise RuntimeError(identity+' failed; no retry')
            for suffix in ['.stdout','.stderr','_PROCESS.json']:accept(out/(identity+suffix))
            receipt=out/(identity+'_COMPLETE.json');b=raw(receipt);c=json.loads(b)
            events.append({'operation':'JSON parse','file':str(receipt),'sha256':sha(b)})
            if c['status']!='PASS' or c['approval_sha256']!=sha(ab) or c['registry_sha256']!=sha(rb):raise ValueError('child binding')
            accept(receipt)
            for n,h in c['outputs'].items():
                accept(out/n,h)
            if phase=='preflight':predecessor=sha(b)
            check_budget()
        # Reauthenticate the entire finite consumed-input union, without parsing arrays.
        from provenance_v2 import Access
        final_access=Access(args.project,r['scopes']['all'])
        for n in final_access.spec['files']:check_budget();final_access.file(n)
        for archive,spec in final_access.spec['archives'].items():
            for member in spec['members']:check_budget();final_access.member(archive,member)
        events.extend(final_access.events)
        finish_bootstrap(args,a,r,sources,ab,rb,events)
        if {p.name for p in out.iterdir() if p.is_file()}!=set(accepted):raise ValueError('unaccepted output inventory')
        for n,h in accepted.items():check_budget();accept(out/n,h)
        check_budget()
        pending=out/'COMPLETE_PENDING.json'
        write(pending,{'reference_contract':r['reference_contract'],'status':'COMPLETE_REQUIRES_INDEPENDENT_REVIEW','elapsed_seconds':time.monotonic()-start,'approval_sha256':sha(ab),'registry_sha256':sha(rb),'preflight_sha256':predecessor,'warm_records':49,'cold_records':7,'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'events':events,'load_average_end':os.getloadavg(),'outputs':accepted})
        check_budget()
        pending.rename(out/'COMPLETE.json')
        try:check_budget()
        except BaseException:
            (out/'COMPLETE.json').rename(out/'COMPLETE_REJECTED_BUDGET.json');raise
    except BaseException as e:
        write(out/'FAILURE.json',{'exception':repr(e),'traceback':traceback.format_exc(),'processes':processes,'events':events});raise
def main():
    p=argparse.ArgumentParser()
    for k in ['project','approval','approval-sha256','output']:p.add_argument('--'+k,required=True)
    p.add_argument('--phase',choices=['parent','preflight','cold','warm'],default='parent');p.add_argument('--route');p.add_argument('--predecessor-sha256')
    args=p.parse_args();a,r,sources,ab,rb=authorize(args)
    if (args.phase=='cold')!=(args.route is not None) or (args.route and args.route not in r['routes']):raise ValueError('phase/route')
    if (args.phase in ['cold','warm'])!=(args.predecessor_sha256 is not None):raise ValueError('phase/predecessor')
    saved={}
    try:
        saved,events=execute_sources(sources)
        events[:0]=[{'operation':'source file read','file':str(H/n),'sha256':sha(b)} for n,b in sources.items()]+[{'operation':'JSON parse','file':args.approval,'sha256':sha(ab)},{'operation':'JSON parse','file':str(H/'REGISTRY_v5.json'),'sha256':sha(rb)}]
        def timeout(*unused):raise TimeoutError('request budget')
        signal.signal(signal.SIGALRM,timeout)
        if args.phase=='parent':parent(args,a,r,sources,ab,rb,events)
        else:child(args,a,r,sources,ab,rb,events)
    finally:restore(saved)
if __name__=='__main__':main()
