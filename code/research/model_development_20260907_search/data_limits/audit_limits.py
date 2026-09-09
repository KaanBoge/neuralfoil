"""Descriptive, non-fitting audit of exposed data. Never opens unscored files."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import zipfile

import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[1]
V2=PROJECT/'model_development_20260906_v2'
sys.path.insert(0,str(V2))
import develop_v2 as v


def describe(x):
    x=np.asarray(x,dtype=float)
    x=x[np.isfinite(x)]
    if not len(x):return {'n':0}
    return {'n':len(x),'mean':float(x.mean()),'median':float(np.median(x)),
        'p25':float(np.quantile(x,.25)),'p75':float(np.quantile(x,.75)),
        'p90':float(np.quantile(x,.9)),'p95':float(np.quantile(x,.95)),
        'maximum':float(x.max())}


def exact_analysis(key,y,label,records):
    _,inverse,count=np.unique(key,axis=0,return_inverse=True,return_counts=True)
    contradiction_rows=0;contradiction_groups=0;minimum=0.;pair_ranges=[]
    for g in np.flatnonzero(count>1):
        ix=np.flatnonzero(inverse==g);yy=y[ix];med=np.median(yy);loss=np.abs(yy-med).sum()
        minimum+=loss
        if np.ptp(yy)>0:
            contradiction_rows+=len(ix);contradiction_groups+=1;pair_ranges.append(np.ptp(yy)*1e4)
            for i in ix:
                records.append({'key':label,'cluster':int(g),'nf2_row_id':int(d['nf2_row_id'][i]),
                    'entry':str(d['entry'][i]),'Re':float(d['Re'][i]),'alpha':float(d['alpha'][i]),
                    'measured_CD':float(y[i]),'group_median_CD':float(med),'range_counts':float(np.ptp(yy)*1e4)})
    return {'unique_keys':len(count),'repeated_keys':int((count>1).sum()),
        'rows_in_repeated_keys':int(count[count>1].sum()),'contradictory_keys':contradiction_groups,
        'rows_in_contradictory_keys':contradiction_rows,'empirical_minimum_total_absolute_CD':float(minimum),
        'empirical_minimum_pooled_MAE_counts':float(minimum/len(y)*1e4),
        'contradiction_range_counts':describe(pair_ranges)}


d=v.load_data();n=len(d['MEAS_CD']);y=d['MEAS_CD'];base=d['BASE_CD']
result={'rows':n,'groups':len(set(d['group'])),
 'scope':'Historical8371 and already exposed SG/W; no fitting or unscored measurement reads',
 'near_pair_tolerances_declared_before_results':[
     {'abs_alpha_degrees':.02,'symmetric_relative_Re':.005},
     {'abs_alpha_degrees':.05,'symmetric_relative_Re':.01},
     {'abs_alpha_degrees':.1,'symmetric_relative_Re':.02}]}
records=[]
_,geom=np.unique(d['geometry_stats'],axis=0,return_inverse=True)
keys={'X9_exact_float64':d['X9'],'X16_exact_float64':d['X16'],'X24_exact_float64':d['X24'],
    'geometry_stats_Re_alpha_exact':np.column_stack([geom,d['Re'],d['alpha']])}
result['exact']={k:exact_analysis(key,y,k,records) for k,key in keys.items()}
pd.DataFrame(records).to_csv(OUT/'exact_contradictions.csv',index=False)

# Exact same coordinate-file SHA is deliberately stricter than nominal group.
# No near-neighbor model is fitted. All qualifying unordered pairs are retained.
pairs=[]
for gh in sorted(set(d['geometry_hash'])):
    ids=np.flatnonzero(d['geometry_hash']==gh)
    ii,jj=np.triu_indices(len(ids),1);a,b=ids[ii],ids[jj]
    da=np.abs(d['alpha'][a]-d['alpha'][b]);dr=np.abs(d['Re'][a]-d['Re'][b])/((d['Re'][a]+d['Re'][b])/2)
    keep=(da<=.1+1e-12)&(dr<=.02+1e-12)
    for i,j,aa,rr in zip(a[keep],b[keep],da[keep],dr[keep]):
        pairs.append({'i':int(i),'j':int(j),'row_id_i':int(d['nf2_row_id'][i]),'row_id_j':int(d['nf2_row_id'][j]),
            'entry_i':str(d['entry'][i]),'entry_j':str(d['entry'][j]),'same_source':bool(d['source'][i]==d['source'][j]),
            'same_entry':bool(d['entry'][i]==d['entry'][j]),'delta_alpha':float(aa),'relative_delta_Re':float(rr),
            'measured_difference_counts':float(abs(y[i]-y[j])*1e4),
            'mean8_difference_counts':float(abs(base[i]-base[j])*1e4),
            'residual_difference_counts':float(abs((y[i]-base[i])-(y[j]-base[j]))*1e4),
            'residual_sign_differs':bool((y[i]-base[i])*(y[j]-base[j])<0)})
pf=pd.DataFrame(pairs);pf.to_csv(OUT/'near_condition_pairs.csv',index=False)
result['near_pairs']=[]
for rule in result['near_pair_tolerances_declared_before_results']:
    f=pf[(pf.delta_alpha<=rule['abs_alpha_degrees']+1e-12)&(pf.relative_delta_Re<=rule['symmetric_relative_Re']+1e-12)]
    for scope,sub in [('all',f),('same_source',f[f.same_source]),('cross_source',f[~f.same_source])]:
        result['near_pairs'].append({**rule,'scope':scope,'pairs':len(sub),
            'unique_rows':len(set(sub.i)|set(sub.j)),
            'measurement_difference_counts':describe(sub.measured_difference_counts),
            'baseline_difference_counts':describe(sub.mean8_difference_counts),
            'residual_difference_counts':describe(sub.residual_difference_counts),
            'opposite_residual_sign_pairs':int(sub.residual_sign_differs.sum())})

rawpath=PROJECT/'validation_extension/export_intake_20260906/payload_n805d74v/NeuralFoil-export-starter-2026-09-06/scratchpad/lsat/lsat-corpus.csv'
wanted={int(i):k for k,i in enumerate(d['raw_row_id'])};u=np.full(n,np.nan)
# Parse only explicitly selected historical row IDs, not other corpus outcomes.
with rawpath.open() as stream:
    header=next(csv.reader([next(stream)]))
    for i,line in enumerate(stream):
        if i not in wanted:continue
        row=dict(zip(header,next(csv.reader([line]))));k=wanted[i]
        assert row['source']==d['source'][k] and row['airfoil']==d['af'][k]
        assert row['config']=='clean' and float(row['CD'])==y[k]
        if row['u_cd_span']:u[k]=float(row['u_cd_span'])
hist=pd.DataFrame({'source':d['source'],'entry':d['entry'],'nf2_row_id':d['nf2_row_id'],
    'span_half_counts':u*1e4,'baseline_error_counts':np.abs(y-base)*1e4})
# Verify zero station-spread records against the historical Volume 3 source.
# No other source archives or new outcome files are opened here.
zero_ids=np.flatnonzero(np.isfinite(u)&(u==0))
zero_lookup={(str(d['af'][i]),float(d['Re'][i]),float(d['alpha'][i]),float(d['MEAS_CL'][i]),float(y[i])):i for i in zero_ids}
station_records=[];qualified_metadata=[]
with zipfile.ZipFile(rawpath.parent/'volume03.zip') as z:
    lines=z.read('volume03/DRAG03.TXT').decode('latin1').splitlines()
af=comment=builder='';re_value=0.
for pos,line in enumerate(lines):
    clean=line.strip()
    if clean.startswith('Airfoil:'):af=clean.split(':',1)[1].strip();comment=''
    elif clean.startswith('Builder:'):builder=clean.split(':',1)[1].strip()
    elif clean.startswith('Comment:'):comment=clean.split(':',1)[1].strip()
    elif clean.startswith('Average Reynolds'):
        re_value=float(lines[pos+1])
        if 'open bay' in comment or 'chord' in comment or 'LTPT' in comment:
            ix=np.flatnonzero((d['source']=='vol3')&(d['af']==af)&(d['Re']==re_value))
            if len(ix):qualified_metadata.append({'airfoil':af,'Re':re_value,'comment':comment,
                'builder':builder,'source_Re_header_line':pos+1,'historical_rows':len(ix),
                'nf2_row_ids':d['nf2_row_id'][ix].tolist()})
    elif clean.lower().startswith('alpha'):
        for line_no in range(pos+1,len(lines)):
            tokens=lines[line_no].split()
            try:values=list(map(float,tokens))
            except ValueError:break
            if len(values)<3:break
            key=(af,re_value,*values[:3])
            if key in zero_lookup:
                i=zero_lookup[key]
                station_records.append({'nf2_row_id':int(d['nf2_row_id'][i]),'entry':str(d['entry'][i]),
                    'source_line':line_no+1,'measured_CD':float(y[i]),'station_count':len(values[3:]),
                    'all_stations_zero':bool(len(values)>3 and np.all(np.array(values[3:])==0)),
                    'raw_line':lines[line_no],'comment':comment})
zero_verified={row['nf2_row_id'] for row in station_records if row['all_stations_zero']}
assert zero_verified==set(map(int,d['nf2_row_id'][zero_ids]))
pd.DataFrame(station_records).to_csv(OUT/'zero_station_placeholders.csv',index=False)
result['station_placeholder_issue']={'historical_rows':len(zero_ids),'all_verified_in_raw_source':True,
    'by_entry':dict(zip(*[a.tolist() for a in np.unique(d['entry'][zero_ids],return_counts=True)])),
    'meaning':'Positive central CD with all span station fields zero; raw half-span zero is not a usable uncertainty observation. Do not alter central CD.'}
result['qualified_clean_metadata']=qualified_metadata
hist['validated_span_half_counts']=hist.span_half_counts.where(~hist.nf2_row_id.isin(zero_verified))
oof=pd.read_csv(V2/'results/primary_oof.csv')[['nf2_row_id','guarded_pooled']]
hist=hist.merge(oof,on='nf2_row_id',validate='one_to_one')
assert np.array_equal(hist.nf2_row_id,d['nf2_row_id'])
hist['cycle2_oof_error_counts']=np.abs(hist.guarded_pooled-y)*1e4
result['span']={}
for source,sub in hist.groupby('source'):
    avail=sub.span_half_counts.notna()
    result['span'][source]={'rows':len(sub),'missing_rows':int((~avail).sum()),
        'half_span_counts':describe(sub.span_half_counts),
        'validated_available_rows':int(sub.validated_span_half_counts.notna().sum()),
        'validated_half_span_counts':describe(sub.validated_span_half_counts),
        'zero_half_span_rows':int((sub.span_half_counts==0).sum()),
        'descriptive_rows_error_le_half_span':int((sub.loc[avail,'cycle2_oof_error_counts']<=sub.loc[avail,'span_half_counts']).sum()),
        'warning':'Half station spread is not a standard deviation, confidence interval, bias bound, or total measurement uncertainty.'}
hist.drop(columns=['guarded_pooled']).to_csv(OUT/'historical_half_spread.csv',index=False)

loss=np.maximum(.5*base-y,0)+np.maximum(y-2*base,0)
result['bounded_correction_oracle']={'bound':'[0.5*mean8,2*mean8]',
    'rows_below_lower_bound':int((y<.5*base).sum()),'rows_above_upper_bound':int((y>2*base).sum()),
    'minimum_pooled_MAE_counts':float(loss.mean()*1e4),
    'by_source':{s:{'rows':int((d['source']==s).sum()),'minimum_MAE_counts':float(loss[d['source']==s].mean()*1e4),
        'outside_bound_rows':int((loss[d['source']==s]>0).sum())} for s in sorted(set(d['source']))},
    'warning':'An outcome-aware per-row oracle for this correction envelope only; not attainable OOF accuracy or a global data noise floor.'}
result['geometry']={'unique_coordinate_file_hashes':len(set(d['geometry_hash'])),
    'unique_geometry_descriptor_vectors':len(set(geom)),
    'entries':len(set(d['entry'])),
    'by_source':{s:{'entries':len(set(d['entry'][d['source']==s])),
        'coordinate_files':len(set(d['geometry_hash'][d['source']==s]))} for s in sorted(set(d['source']))}}

result['exposed']={}
for name,path in [('SG',V2/'external_results/SG_exposed_predictions.csv'),('W',V2/'external_results/W_new_challenge_predictions.csv')]:
    f=pd.read_csv(path);rows=[]
    for config,sub in f.groupby('configuration'):
        ss=sub[sub.eligible];span=ss.spanwise_half_spread_CD*1e4
        rows.append({'configuration':config,'complete_rows':len(sub),'eligible_rows':len(ss),
            'half_span_counts':describe(span),'missing_half_spans':int(span.isna().sum()),
            'baseline_error_counts':describe((ss.xlarge_CD-ss.measured_CD).abs()*1e4),
            'cycle2_error_counts':describe((ss.cycle2_CD-ss.measured_CD).abs()*1e4)})
    eligible=f[f.eligible]
    losses=(eligible.cycle2_CD-eligible.measured_CD).abs()*1e4
    oracle=np.maximum(.5*eligible.mean8_CD-eligible.measured_CD,0)+np.maximum(eligible.measured_CD-2*eligible.mean8_CD,0)
    largest=eligible.loc[losses.idxmax()]
    result['exposed'][name]={'by_configuration':rows,
        'eligible_rows':len(eligible),'bounded_oracle_MAE_counts':float(oracle.mean()*1e4),
        'rows_outside_envelope':int((oracle>0).sum()),
        'largest_error_row':{'configuration':str(largest.configuration),'source_line':int(largest.source_line),
            'alpha':float(largest.alpha),'Re':float(largest.Re),'measured_CD':float(largest.measured_CD),
            'error_counts':float(losses.max()),'share_of_total_absolute_error_percent':float(100*losses.max()/losses.sum())}}

paths=[Path(__file__),V2/'develop_v2.py',v.OLD/'develop_drag.py',v.OLD/'reproduction/dataset_occurrence.npz',
    v.OLD/'methods_audit/entry_group_map.csv',v.OLD/'methods_audit/ambiguous_nf2_row_ids.csv',rawpath,
    V2/'results/primary_oof.csv',V2/'external_results/SG_exposed_predictions.csv',V2/'external_results/W_new_challenge_predictions.csv']
paths.append(rawpath.parent/'volume03.zip')
result['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(OUT/'data_limits.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result,indent=2,allow_nan=False))
