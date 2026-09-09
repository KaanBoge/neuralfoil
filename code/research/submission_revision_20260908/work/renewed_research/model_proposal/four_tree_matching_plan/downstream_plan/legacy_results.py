"""Explicit phase-gated reads of the completed paired-D controls."""
from pathlib import Path
import io
import pandas as pd
import adapter as a

def authenticate(reg,ledger):
    spec=reg['paired_results'];root=a.ROOT/spec['root'];previous=reg['inherited']['replay_sha256'];records={}
    oldreg=a.json_read(root/'REGISTRY.json',spec['registry_sha256'],ledger)
    for n,h in oldreg['sources'].items():
        if Path(n).name!=n:raise ValueError('paired finite source')
        a.read(root/n,h,ledger,'paired source identity')
    for n,h in oldreg['provenance'].items():
        if Path(n).is_absolute() or '..' in Path(n).parts:raise ValueError('paired finite provenance')
        a.read(root/n,h,ledger,'paired historical provenance identity')
    for phase in ['preflight','calibrate','score','assess']:
        entry=spec['phases'][phase];r=a.json_read(root/phase/'COMPLETE.json',entry['complete_sha256'],ledger)
        ap=a.json_read(a.ROOT/entry['approval_path'],entry['approval_sha256'],ledger)
        if (r.get('status')!='COMPLETE' or r.get('phase')!=phase or r.get('registry_sha256')!=spec['registry_sha256'] or r.get('approval_sha256')!=entry['approval_sha256'] or r.get('summary',{}).get('predecessor_sha256')!=previous or (root/phase/'FAILURE.json').exists()):raise ValueError('paired completed phase chain')
        if ap['phase']!=phase or ap['registry_sha256']!=spec['registry_sha256'] or ap['predecessor_sha256']!=previous or ap['actual_execution_authorized'] is not True:raise ValueError('paired approval chain')
        # Byte authentication only. CSV/NPZ targets are not parsed here.
        for n,h in r['outputs'].items():
            if Path(n).name!=n:raise ValueError('paired output path')
            a.read(root/phase/n,h,ledger,'paired output bytes unparsed')
        records[phase]=r;previous=entry['complete_sha256']
    return records

def payload(reg,records,phase,name,current_phase,ledger):
    allowed=(current_phase=='calibrate' and phase=='calibrate' and name.startswith(('calibrator_','membership_')) and name.endswith('.json'))
    allowed|=(current_phase=='assess' and phase in ['score','assess'] and name.endswith('.csv'))
    if not allowed or Path(name).name!=name:raise ValueError('paired control phase role')
    return a.read(a.ROOT/reg['paired_results']['root']/phase/name,records[phase]['outputs'][name],ledger,'paired role controlled payload')
def scalar(reg,records,name,ledger):return a.parse(payload(reg,records,'calibrate',name,'calibrate',ledger),ledger,'paired scalar/'+name)
def table(reg,records,phase,name,ledger):
    raw=payload(reg,records,phase,name,'assess',ledger)
    ledger.append({'operation':'pandas.read_csv','identity':'paired/'+phase+'/'+name,'sha256':a.sha(raw)})
    return pd.read_csv(io.BytesIO(raw),low_memory=False)
