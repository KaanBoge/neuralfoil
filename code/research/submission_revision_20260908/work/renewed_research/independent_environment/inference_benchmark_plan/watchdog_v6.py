"""Bounded observed-RSS monitor with explicit terminal-unavailable handling.

Not continuous/all-instant memory certification. Missing live monitoring remains
fail-closed. Only a reaped zero exit with a prior sample can be provisional.
"""
import subprocess,time
TEXT_BYTES=4096
MAX_EVENTS=32
GRACE_SECONDS=.05

def text(value):
    raw=str(value).encode('utf-8',errors='replace')
    return {'text':raw[:TEXT_BYTES].decode('utf-8',errors='replace'),'truncated':len(raw)>TEXT_BYTES,'original_bytes':len(raw)}

class RSSUnavailable(RuntimeError):
    def __init__(self,observation):
        super().__init__('RSS unavailable; terminal observation required')
        self.observation=observation

class RSSQueryFailure(RuntimeError):
    def __init__(self,observation):
        super().__init__('RSS query failed; no terminal grace')
        self.observation=observation

def rss_bytes(proc,run=subprocess.run,clock=time.monotonic):
    before=proc.poll();start=clock()
    try:r=run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True,timeout=2)
    except BaseException as exc:
        raise RSSQueryFailure({'reason':'query_exception','exception':text(repr(exc)),'stdout':text(getattr(exc,'stdout','')),'stderr':text(getattr(exc,'stderr','')),'started_monotonic':start,'finished_monotonic':clock(),'poll_before':before,'poll_after':proc.poll()}) from exc
    value=r.stdout.strip()
    if r.returncode or not value or not value.isdecimal() or int(value)<=0:
        reason='bad_return_code' if r.returncode else ('empty' if not value else ('nondecimal' if not value.isdecimal() else 'nonpositive'))
        raise RSSUnavailable({'reason':reason,'returncode':r.returncode,'stdout':text(r.stdout),'stderr':text(r.stderr),'started_monotonic':start,'finished_monotonic':clock(),'poll_before':before,'poll_after':proc.poll()})
    return int(value)*1024

def budget(start,max_seconds,size,max_size,clock=time.monotonic):
    if clock()-start>max_seconds:raise TimeoutError('wall budget')
    if size()>max_size:raise RuntimeError('output size stop threshold')

def cleanup(proc):
    """Never mask original monitor evidence with cleanup errors."""
    events=[];failed=False
    def record(action,error=None):
        nonlocal failed
        events.append({'action':action,**({'error':text(repr(error))} if error else {})})
        failed=failed or error is not None
    try:alive=proc.poll() is None
    except BaseException as e:record('poll',e);alive=True
    if alive:
        try:proc.terminate();record('terminate')
        except BaseException as e:record('terminate',e)
    try:proc.wait(timeout=5);record('wait_reaped')
    except BaseException as e:
        record('wait_failed',e)
        try:proc.kill();record('kill')
        except BaseException as k:record('kill',k)
        try:proc.wait(timeout=5);record('wait_after_kill_reaped')
        except BaseException as k:record('wait_after_kill_failed',k)
    return events,failed

def monitor(proc,start,max_seconds,max_rss,size,max_size,clock=time.monotonic,sleep=time.sleep,rss=rss_bytes):
    peak=None;failure=None;events=[];valid_samples=0;terminal_recovered=False
    def observation(value):
        value=dict(value)
        for key in ['started_monotonic','finished_monotonic']:
            if key in value:value[key+'_since_parent_start']=value.pop(key)-start
        return value
    def event(value):
        if len(events)>=MAX_EVENTS:raise RuntimeError('diagnostic ledger capacity')
        events.append(value)
    try:
        while proc.poll() is None:
            try:value=rss(proc)
            except RSSUnavailable as exc:
                event({'event':'RSS_unavailable','observation':observation(exc.observation)})
                budget(start,max_seconds,size,max_size,clock)
                remaining=max_seconds-(clock()-start)
                if remaining<=0:raise TimeoutError('no terminal observation budget')
                exit_code=proc.poll()
                if exit_code is None:
                    grace=min(GRACE_SECONDS,remaining)
                    event({'event':'terminal_wait','max_seconds':grace})
                    try:exit_code=proc.wait(timeout=grace)
                    except subprocess.TimeoutExpired:raise RuntimeError('RSS unavailable while child remains live')
                else:
                    # Explicitly reap a child already observed terminal.
                    exit_code=proc.wait(timeout=min(GRACE_SECONDS,remaining))
                budget(start,max_seconds,size,max_size,clock)
                event({'event':'terminal_observed','exit_code':exit_code})
                if exit_code!=0:raise RuntimeError('nonzero terminal exit '+str(exit_code))
                if not valid_samples:raise RuntimeError('terminal RSS unavailable without prior valid sample')
                if peak>max_rss:raise MemoryError('RSS stop threshold')
                terminal_recovered=True
                break
            except RSSQueryFailure as exc:
                event({'event':'RSS_query_failure','observation':observation(exc.observation)});raise
            if type(value) is not int or value<=0:raise RuntimeError('invalid RSS sample')
            valid_samples+=1;peak=value if peak is None else max(peak,value)
            budget(start,max_seconds,size,max_size,clock)
            if peak>max_rss:raise MemoryError('RSS stop threshold')
            sleep(.1)
        budget(start,max_seconds,size,max_size,clock)
        if proc.returncode:raise RuntimeError('child exit '+str(proc.returncode))
    except BaseException as exc:failure=text(repr(exc))['text']
    finally:
        cleanup_events,cleanup_failed=cleanup(proc)
        if cleanup_failed and failure is None:failure='cleanup exception; see cleanup_events'
    return {'exit_code':proc.returncode,'peak_sampled_RSS_bytes':peak,'RSS_available':peak is not None,'valid_RSS_samples':valid_samples,'terminal_unavailable_recovered':terminal_recovered,'receipt_self_peak_required':True,'failure':failure,'RSS_diagnostics':events,'cleanup_events':cleanup_events,'scope':'periodic parent RSS plus separately authenticated child self peak; not continuous memory certification'}
