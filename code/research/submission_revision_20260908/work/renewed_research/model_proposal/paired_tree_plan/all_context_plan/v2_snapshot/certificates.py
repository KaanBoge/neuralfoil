"""One fresh subprocess per context; inert until an exact real-phase approval."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import adapter as a

def phase_inputs(args,ledger):
    reg=a.json_read(a.HERE/a.REGISTRY_NAME,args.registry_sha256,ledger)
    ap=a.authenticate(reg,args.registry_sha256,args.approval,args.approval_sha256,args.phase,ledger)
    table=a.json_read(a.HERE/'CONTEXTS.json',reg['sources']['CONTEXTS.json'],ledger)
    manifest=a.json_read(a.ROOT/a.MANIFEST,a.MANIFEST_SHA,ledger);a.verify_contexts(table,manifest)
    return reg,ap,table

def child(args):
    if args.context not in a.CONTEXTS[:-1]:raise ValueError('only15newcontexts; final must inherit')
    if a.safe(args.output)!=a.HERE/args.phase/args.context:raise ValueError('fixed child destination')
    def work(out,ledger,outputs,deadline):
        reg,ap,table=phase_inputs(args,ledger);row=next(r for r in table if r['context']==args.context)
        old=a.json_read(a.ROOT/a.STAGE0,a.STAGE0_SHA,ledger)
        with a.sole_modules(ledger) as (ms,oldreg):
            s,run=ms['support'],ms['runner']
            modelpath=a.ROOT/'independent_environment/bounds_extraction'/row['member']
            raw=a.read(modelpath,row['sha256'],ledger,'sole context NPZ bytes')
            if args.phase=='certificates_produce':
                arrays=run.load_arrays(raw,ledger);budget=s.Budget(max(.001,deadline-time.monotonic()))
                def checkpoint(domain,n,obj):outputs[f'checkpoint_{domain}_{n:03d}.json']=s.exclusive(out/f'checkpoint_{domain}_{n:03d}.json',obj)
                cert=ms['producer'].construct(arrays,s.dependencies(ledger),budget,checkpoint,model_sha=row['sha256'])
                a.stage0_equal(cert,old,row,s.unfraction)
                h,size=run.large_exclusive(out/'certificate.json',cert);outputs['certificate.json']=outputs['certificate.json.partial']=h
                result={'certificate_sha256':h,'certificate_bytes':size,'counts':cert['counts'],'summary':cert['summary'],'estimated_owned_peak_bytes':budget.peak}
            else:
                producer=a.json_read(a.HERE/'certificates_produce/COMPLETE.json',ap['predecessor_sha256'],ledger)
                entry=producer['summary']['contexts'][args.context]
                previous=a.json_read(a.HERE/'certificates_produce'/args.context/'COMPLETE.json',entry['complete_sha256'],ledger)
                pin=previous['outputs']['certificate.json']
                cr=a.read(a.HERE/'certificates_produce'/args.context/'certificate.json',pin,ledger,'context certificate')
                checkerpath=ms['replay_wrapper'].CHECKER;oraclepath=ms['replay_wrapper'].ORACLE
                checker=a.read(a.ROOT/checkerpath,oldreg['dependencies'][checkerpath],ledger)
                oracle=a.read(a.ROOT/oraclepath,oldreg['dependencies'][oraclepath],ledger)
                cert,checked,memory=ms['replay_wrapper'].replay_buffers(cr,raw,checker,oracle,oldreg['dependencies'][oraclepath],ledger,outputs,out,row['sha256'],deadline)
                a.stage0_equal(cert,old,row,s.unfraction)
                outputs['REPLAY.json']=s.exclusive(out/'REPLAY.json',checked)
                result={'certificate_sha256':pin,'producer_complete_sha256':entry['complete_sha256'],'counts':checked['counts'],'summary':checked['summary'],'memory':memory,'status':'PASS_CONTEXT_REPLAY'}
                a.read(a.HERE/'certificates_produce/COMPLETE.json',ap['predecessor_sha256'],ledger,'end producer aggregate authentication')
                a.read(a.HERE/'certificates_produce'/args.context/'COMPLETE.json',entry['complete_sha256'],ledger,'end producer context authentication')
                a.read(a.HERE/'certificates_produce'/args.context/'certificate.json',pin,ledger,'end certificate authentication')
            a.read(modelpath,row['sha256'],ledger,'end model authentication')
        a.authenticate(reg,args.registry_sha256,args.approval,args.approval_sha256,args.phase,ledger)
        return dict(result,context=args.context,model_sha256=row['sha256'],features_targets_loaded=0,fits=0)
    a.reserve_child(args.phase,args.context)
    def guarded(out,ledger,outputs,deadline):
        with a.storage_guard(out,a.CHILD_CAPS[args.phase]):return work(out,ledger,outputs,deadline)
    return a.attempt(args.output,{'phase':args.phase,'context':args.context,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256},guarded)

def run_child(command,remaining):
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:return _communicate(p,remaining)
    except BaseException as exc:
        p.terminate()
        try:stdout,stderr=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:p.kill();stdout,stderr=p.communicate()
        return p.returncode,stdout.decode(errors='replace'),stderr.decode(errors='replace'),repr(exc)
def _communicate(p,remaining):
    stdout,stderr=p.communicate(timeout=remaining);return p.returncode,stdout.decode(errors='replace'),stderr.decode(errors='replace'),None

def main_phase(args):
    def work(out,ledger,outputs,deadline):
        reg,ap,table=phase_inputs(args,ledger)
        disk=a.disk_preflight(out);entries={};states={c:'NOT_RUN' for c in a.CONTEXTS};active=None
        if args.phase=='certificates_replay':
            prior=a.certificate_chain('certificates_produce',ap['predecessor_sha256'],args.registry_sha256,ledger)
        entries['final']=a.inherited_final(ledger,args.phase=='certificates_replay')
        states['final']='INHERITED_AUTHENTICATED'
        try:
            for row in table[:-1]:
                context=row['context'];active=context;left=deadline-time.monotonic()
                if left<=0:raise TimeoutError('aggregate900second guard')
                reservation=a.reserve_child(args.phase,context)
                outputs[f'reservation_{context}.json']=a.save(out/f'reservation_{context}.json',reservation)
                command=[sys.executable,'-B',str(a.HERE/'certificates.py'),args.phase,'--child','--context',context,'--registry-sha256',args.registry_sha256,'--approval',str(a.safe(args.approval)),'--approval-sha256',args.approval_sha256,'--output',str(out/context)]
                states[context]='RUNNING'
                code,stdout,stderr,error=run_child(command,left)
                outputs[f'process_{context}.json']=a.save(out/f'process_{context}.json',{'returncode':code,'stdout':stdout,'stderr':stderr,'interruption':error})
                if error is not None or code!=0:raise RuntimeError('context failed; no retry: '+context)
                raw=(out/context/'COMPLETE.json').read_bytes()
                ledger.append({'path':str(out/context/'COMPLETE.json'),'sha256':a.sha(raw),'operation':'new child completion read'})
                record=a.parse(raw,ledger,'child completion')
                if record['status']!='COMPLETE' or record['summary']['context']!=context or record['summary']['model_sha256']!=row['sha256']:raise ValueError('child identity')
                a.authenticate_outputs(out/context,record,ledger)
                entries[context]={'complete_sha256':a.sha(raw),**record['summary']}
                outputs[f'context_{context}.json']=a.save(out/f'context_{context}.json',entries[context])
                states[context]='COMPLETE';active=None;a.extension_usage()
        except BaseException:
            if active is not None:states[active]='FAILED'
            outputs['CONTEXT_STATUS.json']=a.save(out/'CONTEXT_STATUS.json',states)
            raise
        outputs['CONTEXT_STATUS.json']=a.save(out/'CONTEXT_STATUS.json',states)
        if set(entries)!=set(a.CONTEXTS):raise ValueError('sixteen context barrier')
        a.authenticate(reg,args.registry_sha256,args.approval,args.approval_sha256,args.phase,ledger)
        if a.inherited_final(ledger,args.phase=='certificates_replay')!=entries['final']:raise ValueError('end inherited final changed')
        for context in a.CONTEXTS[:-1]:
            record=a.json_read(out/context/'COMPLETE.json',entries[context]['complete_sha256'],ledger)
            a.authenticate_outputs(out/context,record,ledger)
        if args.phase=='certificates_replay':a.certificate_chain('certificates_produce',ap['predecessor_sha256'],args.registry_sha256,ledger)
        return {'contexts':entries,'predecessor_sha256':ap.get('predecessor_sha256'),'disk_preflight':disk,'logical_output_bytes':a.extension_usage(),'fresh_contexts':15,'inherited_contexts':1,'features_targets_loaded':0,'fits':0}
    return a.attempt(a.HERE/args.phase,{'phase':args.phase,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256},work)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['certificates_produce','certificates_replay'])
    for k in ('registry-sha256','approval','approval-sha256'):p.add_argument('--'+k,required=True)
    p.add_argument('--child',action='store_true');p.add_argument('--context');p.add_argument('--output')
    args=p.parse_args();print(json.dumps(child(args) if args.child else main_phase(args),sort_keys=True))
