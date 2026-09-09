"""Fail-closed child monitor with guaranteed terminate/kill/reap cleanup."""
import subprocess,time
def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
    else:proc.wait()
def rss_bytes(proc,run=subprocess.run):
    r=run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True)
    value=r.stdout.strip()
    if r.returncode or not value or not value.isdecimal() or int(value)<=0:
        if proc.poll() is not None:return None
        raise RuntimeError('RSS monitor unavailable while child alive')
    return int(value)*1024
def monitor(proc,start,max_seconds,max_rss,size,max_size,clock=time.monotonic,sleep=time.sleep,rss=rss_bytes):
    peak=None;failure=None
    try:
        while proc.poll() is None:
            value=rss(proc)
            if value is not None:peak=value if peak is None else max(peak,value)
            if clock()-start>max_seconds:raise TimeoutError('wall budget')
            if peak is not None and peak>max_rss:raise MemoryError('RSS stop threshold')
            if size()>max_size:raise RuntimeError('output size stop threshold')
            sleep(.1)
        if proc.returncode:raise RuntimeError('child exit '+str(proc.returncode))
    except BaseException as e:failure=repr(e)
    finally:stop(proc)
    return {'exit_code':proc.returncode,'peak_sampled_RSS_bytes':peak,'RSS_available':peak is not None,'failure':failure}
