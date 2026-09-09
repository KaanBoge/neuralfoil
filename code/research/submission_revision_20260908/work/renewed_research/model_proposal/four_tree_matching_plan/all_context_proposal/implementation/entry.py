"""Separate approval required. No scientific work at import."""
import argparse,hashlib,json,os,signal,sys,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
def boot(args):
    raw=(HERE/'REGISTRY_v3.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.registry_sha256:raise ValueError('registry pin')
    reg=json.loads(raw)
    if reg.get('schema')!='FOUR_TREE_ALL_CONTEXT_SOURCE_V1':raise ValueError('registry schema')
    sources={}
    for n,h in reg['sources'].items():
        if Path(n).name!=n or (HERE/n).is_symlink():raise ValueError('source path')
        b=(HERE/n).read_bytes()
        if hashlib.sha256(b).hexdigest()!=h:raise ValueError('local source binding')
        sources[n]=b
    if sources['entry.py']!=Path(__file__).read_bytes():raise ValueError('executing entry')
    s=types.ModuleType('context_support_authenticated');s.__file__=str(HERE/'context_support.py');exec(compile(sources['context_support.py'],s.__file__,'exec'),s.__dict__)
    s.DEADLINE=getattr(args,'_deadline',None)
    ledger=[];s.authenticate(reg,args.registry_sha256,ledger)
    ap=s.parse(s.read(HERE/('ROOT_'+args.phase.upper()+'_APPROVAL.json'),args.approval_sha256,ledger));s.strict_approval(ap,args.registry_sha256,args.phase)
    if any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('single worker runtime')
    ext={k:s.read(ROOT/e['path'],e['sha256'],ledger) for k,e in reg['external_sources'].items()}
    io=s.module(ext['io'],'io_authenticated',ROOT/reg['external_sources']['io']['path']);return reg,sources,ext,s,io,ap,ledger
def child(args):
    started=time.monotonic();reg,sources,ext,s,io,ap,ledger=boot(args)
    if args.context not in s.CONTEXTS[:-1]:raise ValueError('fixed new child context')
    phase=HERE/args.phase;token=s.parse(s.read(phase/'TOKEN.json',args.token_sha256,ledger))
    if token!={'parent_pid':os.getppid(),'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'phase':args.phase}:raise ValueError('owned child token')
    row=reg['contexts'][s.CONTEXTS.index(args.context)];deadline=started+900;s.reserve();store=s.store_type(io)(phase/args.context,deadline)
    meta={'phase':args.phase,'context':args.context,'model_sha256':row['model_sha256'],'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'pid':os.getpid(),'parent_pid':os.getppid()}
    old=signal.getsignal(signal.SIGALRM)
    def expired(*a):raise TimeoutError('900 second child')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:
        store.write_json('ATTEMPT.json',meta)
        stage=s.parse(s.read(ROOT/reg['metadata']['stage0']['path'],reg['metadata']['stage0']['sha256'],ledger));model=ROOT/'independent_environment/bounds_extraction'/row['member']
        sourcebytes=sum(map(len,sources.values()))+sum(map(len,ext.values()))
        if args.phase=='certificates_produce':
            p=s.module(ext['producer'],'context_pure_producer',ROOT/reg['external_sources']['producer']['path']);loader=s.module(ext['producer_entry'],'context_array_intake',ROOT/reg['external_sources']['producer_entry']['path'])
            budget=p.Budget(900);budget.started=started;size=model.stat().st_size
            if size>8*2**20:raise MemoryError('compressed payload cap')
            budget.check(p.memory_plan(4*2**20,size,sourcebytes)['estimated_owned_bytes'])
            raw=s.read(model,row['model_sha256'],ledger,8*2**20);arrays=loader.load_arrays(raw,p,ledger)
            cert=p.construct(arrays,budget,model_sha=row['model_sha256'],source_bytes=sourcebytes,input_bytes=len(raw));s.compare(cert,row,stage)
            store.write_json('certificate.json',cert);summary={k:cert[k] for k in ('counts','stage0','original_adjacent','final')};summary['owned_peak']=budget.peak
        else:
            prior=s.parse(s.read(HERE/'certificates_produce/COMPLETE.json',ap['producer_complete_sha256'],ledger));item=prior['contexts'][args.context]
            cp=HERE/'certificates_produce'/args.context;pc=s.parse(s.read(cp/'COMPLETE.json',item['complete_sha256'],ledger));s.verify_outputs(cp,pc,ledger)
            if pc['model_sha256']!=row['model_sha256'] or pc['registry_sha256']!=args.registry_sha256 or pc['summary']!=item['summary']:raise ValueError('exact child producer binding')
            checker=s.module(ext['checker'],'context_independent_checker',ROOT/reg['external_sources']['checker']['path']);loader=s.module(ext['checker_entry'],'context_independent_loader',ROOT/reg['external_sources']['checker_entry']['path'])
            # The inherited intake's ledger identity is a module constant only;
            # no numerical function/global is replaced or AST rewritten.
            loader.MODEL_SHA=row['model_sha256']
            certpath=cp/'certificate.json';size=model.stat().st_size
            if size>8*2**20 or certpath.stat().st_size>checker.INPUT_CAP:raise MemoryError('serialized input cap')
            pre=checker.owned_estimate(4*2**20,sourcebytes+size,certpath.stat().st_size)
            if pre>256*2**20:raise MemoryError('pre-input replay admission')
            cr=s.read(certpath,pc['outputs']['certificate.json'],ledger,checker.INPUT_CAP)
            cert,allocation=checker.parse_certificate(cr,array_bytes=4*2**20,source_bytes=sourcebytes+size)
            raw=s.read(model,row['model_sha256'],ledger,8*2**20);arrays=loader.independent_arrays(raw,ledger)
            result=checker.check(cert,arrays,deadline,expected_model_sha=row['model_sha256'],source_bytes=sourcebytes+len(raw),input_bytes=len(cr),parsed_bytes=allocation);s.compare(result,row,stage)
            for k in ('counts','stage0','original_adjacent','final'):
                if result[k]!=pc['summary'][k]:raise ValueError('producer independent replay mismatch')
            store.write_json('REPLAY.json',result);summary={k:result[k] for k in ('counts','stage0','original_adjacent','final')};summary.update(owned_peak=max(pre,checker.owned_estimate(4*2**20,sourcebytes+size,len(cr),allocation)),producer_complete_sha256=item['complete_sha256'],certificate_sha256=pc['outputs']['certificate.json'])
            s.stream(cp/'COMPLETE.json',item['complete_sha256'],ledger);s.verify_outputs(cp,pc,ledger)
        s.stream(model,row['model_sha256'],ledger);s.authenticate(reg,args.registry_sha256,ledger);s.read(HERE/('ROOT_'+args.phase.upper()+'_APPROVAL.json'),args.approval_sha256,ledger);store.verify_outputs(ledger)
        store.write_json('ACCESS.json',ledger);store.write_json('COMPLETE.json',dict(meta,status='COMPLETE',elapsed_seconds=time.monotonic()-started,outputs=dict(store.outputs),summary=summary))
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,0);store.write_json('FAILURE.json',dict(meta,error=repr(e),outputs=dict(store.outputs),last_access=ledger[-20:]),emergency=True);raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
def parent(args):
    started=time.monotonic();args._started=started;args._deadline=started+900
    old=signal.getsignal(signal.SIGALRM)
    def expired(*unused):raise TimeoutError('900 second aggregate including bootstrap and final authentication')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:return parent_work(args)
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
def parent_work(args):
    started=args._started;reg,sources,ext,s,io,ap,ledger=boot(args);deadline=args._deadline
    store=s.store_type(io)(HERE/args.phase,deadline,cap=s.CAP);statuses={c:'NOT_RUN' for c in s.CONTEXTS};entries={}
    try:
        store.write_json('ATTEMPT.json',{'phase':args.phase,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256})
        token={'parent_pid':os.getpid(),'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'phase':args.phase};tp,_=store.write_json('TOKEN.json',token)
        manifest=s.parse(s.read(ROOT/reg['metadata']['manifest']['path'],reg['metadata']['manifest']['sha256'],ledger));s.validate_contexts(reg['contexts'],manifest)
        if args.phase=='certificates_replay':
            previous=s.parse(s.read(HERE/'certificates_produce/COMPLETE.json',ap['producer_complete_sha256'],ledger));verify_phase(previous,s,ledger,args.registry_sha256,reg)
        runner=s.module(sources['processes.py'],'fresh_context_processes',HERE/'processes.py')
        for context in s.CONTEXTS[:-1]:
            s.reserve();statuses[context]='RUNNING'
            command=[sys.executable,'-B',str(HERE/'entry.py'),'--registry-sha256',args.registry_sha256,'--approval-sha256',args.approval_sha256,'--phase',args.phase,'--context',context,'--token-sha256',tp]
            runner.run(command,store.root,context,deadline,s)
            path=store.root/context/'COMPLETE.json';raw=path.read_bytes();r=s.parse(raw);pin=s.sha(raw);s.verify_outputs(path.parent,r,ledger)
            if r['status']!='COMPLETE' or r['context']!=context or r['registry_sha256']!=args.registry_sha256 or r['approval_sha256']!=args.approval_sha256:raise ValueError('completed child identity')
            entries[context]={'complete_sha256':pin,'summary':r['summary']};statuses[context]='COMPLETE'
        entries['final']=s.inherited(reg,ledger);statuses['final']='INHERITED_AUTHENTICATED'
        s.authenticate(reg,args.registry_sha256,ledger);s.read(HERE/('ROOT_'+args.phase.upper()+'_APPROVAL.json'),args.approval_sha256,ledger)
        for c,e in entries.items():
            if c!='final':
                path=store.root/c/'COMPLETE.json';r=s.parse(s.read(path,e['complete_sha256'],ledger));s.verify_outputs(path.parent,r,ledger)
        if args.phase=='certificates_replay':verify_phase(previous,s,ledger,args.registry_sha256,reg);s.read(HERE/'certificates_produce/COMPLETE.json',ap['producer_complete_sha256'],ledger)
        for path in store.root.glob('*.txt'):
            store.outputs[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        store.verify_outputs(ledger);store.write_json('CONTEXT_STATUS.json',statuses);store.write_json('ACCESS.json',ledger)
        store.write_json('COMPLETE.json',{'status':'COMPLETE','phase':args.phase,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'elapsed_seconds':time.monotonic()-started,'contexts':entries,'outputs':dict(store.outputs),'logical_output_bytes_before_completion':s.usage(),'producer_complete_sha256':ap.get('producer_complete_sha256'),'fresh_contexts':15,'inherited_contexts':1,'fits':0,'features_targets_loaded':0,'R_used':False})
    except BaseException as e:
        for c in statuses:
            if statuses[c]=='RUNNING':statuses[c]='FAILED'
        if not (store.root/'CONTEXT_STATUS.json').exists() and not (store.root/'CONTEXT_STATUS.json.partial').exists():store.write_json('CONTEXT_STATUS.json',statuses,emergency=True)
        store.write_json('FAILURE.json',{'error':repr(e),'statuses':statuses,'contexts':entries},emergency=True);raise
def verify_phase(r,s,ledger,regsha,reg):
    if r.get('status')!='COMPLETE' or r.get('phase')!='certificates_produce' or r.get('registry_sha256')!=regsha or set(r['contexts'])!=set(s.CONTEXTS):raise ValueError('complete all-sixteen producer barrier')
    s.verify_outputs(HERE/'certificates_produce',r,ledger)
    for c in s.CONTEXTS[:-1]:
        e=r['contexts'][c];path=HERE/'certificates_produce'/c
        v=s.parse(s.read(path/'COMPLETE.json',e['complete_sha256'],ledger));s.verify_outputs(path,v,ledger)
        if v['status']!='COMPLETE' or v['context']!=c or v['summary']!=e['summary'] or v['registry_sha256']!=regsha or v['approval_sha256']!=r['approval_sha256']:raise ValueError('child producer complete chain')
    app=s.parse(s.read(HERE/'ROOT_CERTIFICATES_PRODUCE_APPROVAL.json',r['approval_sha256'],ledger));s.strict_approval(app,regsha,'certificates_produce')
    if r['contexts']['final']!=s.inherited(reg,ledger):raise ValueError('full inherited final barrier')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry-sha256',required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--phase',choices=['certificates_produce','certificates_replay'],required=True);p.add_argument('--context');p.add_argument('--token-sha256');a=p.parse_args();(child if a.context else parent)(a)
