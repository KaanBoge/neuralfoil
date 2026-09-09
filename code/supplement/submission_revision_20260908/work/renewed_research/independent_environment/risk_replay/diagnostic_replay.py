"""Finish exact-difference inventory without declaring nonexact floats equal."""
import json
import numpy as np
import pandas as pd
import audit

def compare(name,df,keys,records):
    old=audit.csv(audit.P/'assessment'/f'{name}.csv').sort_values(keys).reset_index(drop=True)
    new=audit.roundtrip(df).sort_values(keys).reset_index(drop=True)
    assert len(new)==len(old) and set(new)<=set(old)
    diffs={};counts={}
    for key in new:
        a,b=new[key],old[key]
        if pd.api.types.is_numeric_dtype(a) and a.dtype!=bool:
            x,y=a.to_numpy(),b.to_numpy();assert np.array_equal(np.isnan(x),np.isnan(y))
            diffs[key]=float(np.nanmax(abs(x-y),initial=0));counts[key]=int(((x!=y)&~np.isnan(x)).sum())
            if pd.api.types.is_integer_dtype(a):np.testing.assert_array_equal(x,y)
        else:pd.testing.assert_series_equal(a,b,check_names=False)
    records.append({'table':name,'rows':len(new),'columns_checked':len(new.columns),'max_abs_differences':diffs,'unequal_counts':counts,'exact_after_CSV_roundtrip':not any(counts.values())})

def dump(name,value):
    assert name=='AUDIT.json'
    exact=all(x['exact_after_CSV_roundtrip'] for x in value['tables'])
    value['status']='PASS_EXACT' if exact else 'REPLAY_COMPLETE_WITH_NON_BITWISE_FLOAT_DIFFERENCES'
    value['strict_checker_source_sha256']=audit.sha(audit.HERE/'audit.py')
    value['diagnostic_checker_source_sha256']=audit.sha(__file__)
    value['no_numeric_equality_tolerance_used']=True
    value['note']='All discrete checks remain strict; floating differences are reported, never silently set equal or used to alter scientific promotion thresholds.'
    with (audit.HERE/'METRIC_REPLAY.json').open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
    print(json.dumps({'status':value['status'],'tables':value['tables'],'decisions':value['decisions']},indent=2))

audit.compare=compare
audit.dump=dump
if __name__=='__main__':audit.main()
