"""One owned fresh child, bounded logs and aggregate deadline; no science."""
import os,selectors,signal,subprocess,time
def run(command,root,name,deadline,s):
    if time.monotonic()>=deadline:raise TimeoutError('aggregate before launch')
    with (root/(name+'.stdout.txt')).open('xb') as out,(root/(name+'.stderr.txt')).open('xb') as err:
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
        sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ,out);sel.register(p.stderr,selectors.EVENT_READ,err);local=0
        try:
            while sel.get_map() or p.poll() is None:
                if time.monotonic()>=deadline:raise TimeoutError('aggregate owned child deadline')
                for key,_ in sel.select(.05):
                    b=os.read(key.fd,16384)
                    if not b:sel.unregister(key.fileobj);key.fileobj.close();continue
                    if local+len(b)>s.RESERVE or s.usage()+len(b)>s.CAP-s.RESERVE:raise OSError('prewrite parent log cap')
                    key.data.write(b);key.data.flush();local+=len(b)
            if p.wait()!=0:raise RuntimeError('child failed; no retry')
        finally:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
            sel.close()
            for f in (p.stdout,p.stderr):f.close()
            out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno())
    if time.monotonic()>=deadline:raise TimeoutError('postexit aggregate deadline')
