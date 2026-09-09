"""Opaque finite evidence transport. Never import or interpret archived science."""
import argparse,hashlib,os,time,zipfile
from pathlib import Path
import stream_common as c

class CappedFile:
    def __init__(self,raw,clock):self.raw=raw;self.clock=clock;self.highwater=0
    def write(self,b):
        self.clock.check();end=self.raw.tell()+len(b)
        if end>c.COMPRESSED:raise ValueError('compressed highwater cap')
        n=self.raw.write(b);self.highwater=max(self.highwater,end);return n
    def seek(self,*a):self.clock.check();return self.raw.seek(*a)
    def tell(self):return self.raw.tell()
    def flush(self):self.clock.check();return self.raw.flush()
def info(name):
    z=zipfile.ZipInfo(name,(1980,1,1,0,0,0));z.compress_type=zipfile.ZIP_DEFLATED;z.external_attr=(0o100644)<<16;return z
def run(root,approval,approval_sha,output):
    out=None
    with c.deadline() as clock:
        try:
            rd=c.Reader(root,clock);target=c.path(rd.root,output)
            if target.exists():raise FileExistsError('exclusive attempt directory')
            a,s,rows=c.authorize(rd,approval,approval_sha,'CREATE',output)
            # All admission/stat checks precede first payload open or output creation.
            for r in rows:
                p=c.path(rd.root,r['source'])
                if not p.is_file() or p.stat().st_size!=r['bytes']:raise ValueError('declared payload size')
            manifest={'schema':'v9-saved-evidence-1','selection_sha256':a['selection_sha256'],'claim':s['claim'],'files':{r['target']:{'sha256':r['sha256'],'bytes':r['bytes']} for r in rows}}
            mb=c.encode(manifest);target.mkdir(parents=False);out=target
            c.publish(out/'ATTEMPT.json',{'phase':'CREATE','approval_sha256':approval_sha,'source_pins':a['source_pins'],'selection_sha256':a['selection_sha256'],'scientific_execution':False},clock)
            archive=out/'v9_evidence.zip';raw=archive.open('xb')
            try:
                capped=CappedFile(raw,clock)
                with zipfile.ZipFile(capped,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
                    z.writestr(info('MANIFEST.json'),mb)
                    for r in rows:
                        clock.check();p=c.path(rd.root,r['source']);count=0;h=hashlib.sha256()
                        with p.open('rb') as f,z.open(info(r['target']),'w',force_zip64=True) as dst:
                            while b:=f.read(c.CHUNK):
                                clock.check();count+=len(b)
                                if count>r['bytes']:raise ValueError('source grew during stream')
                                h.update(b);dst.write(b)
                        if count!=r['bytes'] or h.hexdigest()!=r['sha256']:raise ValueError('streamed source mismatch')
                        rd.pins[r['source']]=r['sha256']
                raw.flush();os.fsync(raw.fileno())
            finally:raw.close()
            # Exact source/approval/selection reauthentication, not metadata-only.
            rd.end();ah=hashlib.sha256()
            with archive.open('rb') as f:
                while b:=f.read(c.CHUNK):clock.check();ah.update(b)
            result={'status':'CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING','phase':'CREATE','approval_sha256':approval_sha,'selection_sha256':a['selection_sha256'],'source_pins':a['source_pins'],'archive_sha256':ah.hexdigest(),'archive_bytes':archive.stat().st_size,'manifest_sha256':c.digest(mb),'files':len(rows),'payload_bytes':sum(r['bytes'] for r in rows),'expanded_bytes':sum(r['bytes'] for r in rows)+len(mb),'compressed_highwater':capped.highwater,'seconds':time.monotonic()-clock.start,'scientific_execution':False}
            c.publish(out/'COMPLETE.json',result,clock);return result
        except BaseException as e:c.failure(out,e);raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['root','approval','approval-sha256','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();print(run(a.root,a.approval,a.approval_sha256,a.output))
