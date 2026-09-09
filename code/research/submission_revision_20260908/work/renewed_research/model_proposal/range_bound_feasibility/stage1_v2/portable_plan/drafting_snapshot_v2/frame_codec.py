"""Safe typed DataFrame codec, preserving mixed object scalars without pickle."""
import numpy as np
import pandas as pd

def pack(frame):
    arrays={};schema=[]
    for j,name in enumerate(frame.columns):
        key=f'c{j:03d}';a=frame[name].to_numpy()
        row={'name':name,'key':key,'dtype':str(frame[name].dtype)}
        if a.dtype.kind=='O':
            values=[];kinds=[]
            for value in a:
                if value is None:k,s=0,''
                elif isinstance(value,(str,np.str_)):k,s=1,str(value)
                elif isinstance(value,(bool,np.bool_)):k,s=2,'1' if value else '0'
                elif isinstance(value,(int,np.integer)):k,s=3,str(int(value))
                elif isinstance(value,(float,np.floating)):k,s=4,float(value).hex()
                else:raise ValueError('unsupported object scalar type')
                kinds.append(k);values.append(s)
            arrays[key]=np.array(values,dtype=str);arrays[key+'_kind']=np.array(kinds,dtype=np.uint8)
        elif a.dtype.kind in 'biufUS':arrays[key]=a.copy()
        else:raise ValueError('unsupported frame dtype')
        schema.append(row)
    return arrays,{'columns':schema,'rows':len(frame)}

def unpack(arrays,schema):
    columns={}
    for row in schema['columns']:
        key=row['key'];a=arrays[key]
        if row['dtype']=='object':
            values=[]
            for s,k in zip(a,arrays[key+'_kind']):
                if k==0:v=None
                elif k==1:v=str(s)
                elif k==2:
                    if s not in ('0','1'):raise ValueError('noncanonical bool')
                    v=s=='1'
                elif k==3:v=int(s)
                elif k==4:v=float.fromhex(s)
                else:raise ValueError('unknown object tag')
                values.append(v)
            a=np.array(values,dtype=object)
        if len(a)!=schema['rows']:raise ValueError('frame row alignment')
        columns[row['name']]=a
    return pd.DataFrame(columns)
