"""Scoped authenticated data-reader tracing and exclusive attempt/failure receipts.

One worker only. Patches library entry points, never inherited numeric bodies.
"""
from pathlib import Path
import io,json,os,time,traceback,datetime
import numpy as np
import pandas as pd
import integrity

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

class TracedNPZ:
    def __init__(self,z,event):self.z=z;self.event=event
    @property
    def files(self):return self.z.files
    def __getitem__(self,key):
        value=self.z[key]
        if value.dtype.hasobject:raise ValueError('object member prohibited')
        self.event['members'].append({'name':key,'shape':list(value.shape),'dtype':str(value.dtype),'bytes':int(value.nbytes)})
        return value
    def __iter__(self):return iter(self.files)
    def __len__(self):return len(self.files)
    def __enter__(self):return self
    def __exit__(self,*args):self.z.close()
    def close(self):self.z.close()

class ReaderTrace:
    def __init__(self,inputs):
        self.inputs=inputs;self.events=[];self.by_hash={}
        for path,h in inputs.items():self.by_hash.setdefault(h,[]).append(path)
    def bound_bytes(self,value):
        if isinstance(value,(str,os.PathLike)):
            path=str(Path(value));expected=self.inputs.get(path)
            if expected is None:raise ValueError('unregistered data path')
            raw=Path(path).read_bytes();paths=[path]
        elif isinstance(value,io.BytesIO):
            if value.tell()!=0:raise ValueError('nonzero input buffer offset')
            raw=value.getvalue();expected=integrity.sha(raw);paths=self.by_hash.get(expected)
            if not paths:raise ValueError('unregistered data bytes')
        else:raise ValueError('unsupported data reader source')
        if integrity.sha(raw)!=expected:raise ValueError('data bytes authentication failed')
        return raw,{'source_paths':paths,'sha256':expected,'bytes':len(raw)}
    def load(self,file,*args,**kwargs):
        if kwargs.get('allow_pickle',False):raise ValueError('pickle prohibited')
        raw,event=self.bound_bytes(file);event.update(reader='numpy.load',members=[]);self.events.append(event)
        kwargs['allow_pickle']=False
        z=self.original_np(io.BytesIO(raw),*args,**kwargs)
        if not isinstance(z,np.lib.npyio.NpzFile):raise ValueError('NPZ only')
        return TracedNPZ(z,event)
    def csv(self,file,*args,**kwargs):
        raw,event=self.bound_bytes(file);event['reader']='pandas.read_csv';self.events.append(event)
        table=self.original_pd(io.BytesIO(raw),*args,**kwargs)
        if not isinstance(table,pd.DataFrame):raise ValueError('nonmaterialized CSV reader unsupported')
        event.update(rows=len(table),columns=list(table.columns));return table
    def __enter__(self):
        self.original_np=np.load;self.original_pd=pd.read_csv
        np.load=self.load;pd.read_csv=self.csv;return self
    def __exit__(self,*unused):
        np.load=self.original_np;pd.read_csv=self.original_pd

def write_exclusive(path,value):
    raw=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def run_attempt(args,operation):
    """Retain ordinary exception/timeout evidence; cannot guarantee SIGKILL recovery."""
    output=integrity.new_target(args.output)
    attempt=integrity.new_target(str(output)+'.attempt.json')
    failure=integrity.new_target(str(output)+'.failure.json')
    integrity.new_target(str(output)+'.receipt.json')
    record={'started_UTC':now(),'registry_sha256':args.registry_sha256,
        'approval_path':str(args.approval),'approval_sha256':args.approval_sha256,
        'builder_sha256':integrity.sha(Path(__file__).with_name('build_replay.py').read_bytes()),
        'output':str(output),'scope':'export only; zero fits'}
    write_exclusive(attempt,record);start=time.monotonic()
    try:return operation()
    except BaseException as exc:
        record.update(finished_UTC=now(),elapsed_seconds=time.monotonic()-start,
            exception=repr(exc),traceback=traceback.format_exc(),
            actual_data_reads=getattr(args,'data_reads',[]),partial_archive_preserved=output.exists())
        if output.is_file():
            record['partial_archive_bytes']=output.stat().st_size
            if output.stat().st_size<=integrity.MAX_BYTES:record['partial_archive_sha256']=integrity.sha(output.read_bytes())
        write_exclusive(failure,record)
        raise
