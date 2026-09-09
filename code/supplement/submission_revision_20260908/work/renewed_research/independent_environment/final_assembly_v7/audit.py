from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
import pandas as pd
OUT=Path(__file__).resolve().parent
REV=OUT.parents[3]; ROOT=REV.parent; E=REV/'renewed_manuscript_v7'; R=REV/'work/renewed_research'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[];pins={}
def pin(p,h=None):
    actual=sha(p);pins[str(p)]=actual
    if h is not None:assert actual==h,str(p)
def check(name,value):
    assert value,name
    checks.append(name)
def rows(p):
    return [[c.strip() for c in x.strip().strip('|').split('|')] for x in p.read_text().splitlines() if x.startswith('|')][2:]
def label(s):
    for a,b in [('history_20260906','A'),('history_20260908','B'),('group_20260906','A'),('group_20260908','B'),('strict_source_','Holdout '),('W_new_challenge','W'),('SG_exposed','SG'),('eligible_only/','Eligible '),('_',' '),('/',' ')]:s=s.replace(a,b)
    return s
a=json.loads((E/'work/ASSEMBLY.json').read_text());pin(E/'work/ASSEMBLY.json')
for p,h in a['source_sha256'].items():pin(ROOT/p,h)
for name in ['main','supplement']:pin(E/f'{name}.complete.md',a[f'{name}_sha256'])
pin(E/'assemble_submission.py',a['code_sha256'])
for d in ['risk_displays','measurement_displays']:
    w=json.loads((E/f'work/{d}/MANIFEST.json').read_text())
    for p,h in w['input_sha256'].items():pin(Path(p),h)
    for p,h in w['output_sha256'].items():pin(E/p,h)
for p in [R/'model_proposal/assessment/report.json',R/'measurement_sensitivity/attempt_1/manifest.json']:
    w=json.loads(p.read_text())
    for f,h in w['output_sha256'].items():pin(Path(f) if Path(f).is_absolute() else p.parent/f,h)
NAME='calibrated_incremental_harm_001'; src=R/'model_proposal/assessment'
c=pd.read_csv(src/'calibration_summary.csv',float_precision='round_trip')
expect=[[label(x.context),str(x.groups),str(x.rows),f'{x.endpoint_mean:.6f}',f'{x.upper_bound:.6f}',f'{x.t:.6f}'] for x in c.itertuples()]
check('S29 all 16 rows exact displayed rounding',rows(E/'work/risk_displays/calibration.md')==expect)
p=pd.read_csv(src/'panel_metrics.csv',float_precision='round_trip');p=p[p.candidate.eq(NAME)]
expect=[[label(x.panel),str(x.rows),f'{x.mae_drag_counts:.2f}',f'{x.xlarge_CD_improvement_percent:+.2f}',f'{x.mean8_CD_improvement_percent:+.2f}',f'{100*x.xlarge_CD_worse_fraction:.2f}'] for x in p.itertuples()]
check('S30 all 31 panels six columns exact',rows(E/'work/risk_displays/panels.md')==expect)
b=pd.read_csv(src/'bootstrap.csv',float_precision='round_trip');b=b[b.candidate.eq(NAME)]
expect=[]
for ref,title in [('unpenalized_transfer','Unpenalized transfer'),('half_strength','Established half'),('proper_capped_half','Matched proper half')]:
    for seed in [20260906,20260908]:
        x=b[(b.reference==ref)&(b.assignment==seed)].iloc[0]
        expect.append([title,'A' if seed==20260906 else 'B',f'{x.remaining_MAE_reduction_percent:+.4f}',f'{x.conditional_95pct_lower:+.4f}',f'{x.conditional_95pct_upper:+.4f}'])
check('S31 all six bootstrap comparisons exact',rows(E/'work/risk_displays/bootstrap.md')==expect)
s=R/'measurement_sensitivity/attempt_1';rad=pd.read_csv(s/'radii.csv',float_precision='round_trip');grid=pd.read_csv(s/'grid.csv',float_precision='round_trip'); panels=pd.read_csv(s/'panels.csv')
allrows=rows(E/'work/measurement_displays/complete_row_box_radii.md')
allrows=[r for r in allrows if r[0] not in ['View','---']]
expect=[]
for weight in ['row','equal_bundle']:
    for panel in panels.panel:
        rr=[label(panel)]
        for proc in ['unpenalized_transfer','half_strength']:
            for frac in [0,.09]:
                vals=[]
                for base in ['mean8_CD','xlarge_CD']:
                    x=rad[(rad.panel==panel)&(rad.weighting==weight)&(rad.procedure==proc)&(rad.target_fraction==frac)&(rad.baseline==base)&(rad.uncertainty_model=='row_box')]
                    assert len(x)==1
                    x=x.iloc[0];vals.append(f'{1e4*x.radius_lower_CD:.2f}' if x.radius_status=='finite_bracket' else {'observed_negative':'Fails','observed_zero':'Zero'}[x.radius_status])
                rr.append(' / '.join(vals))
        expect.append(rr)
check('S32 S33 all 62 radius rows 496 radius entries exact',allrows==expect)
counts=pd.read_csv(E/'work/measurement_displays/positive_comparisons.csv')
for x in counts.itertuples():
    z=grid[(grid.procedure==x.procedure)&(grid.weighting=='row')&(grid.target_fraction==x.target_fraction)&(grid.uncertainty_model==x.uncertainty_model)&(grid.epsilon_drag_counts==x.epsilon_drag_counts)]
    assert len(z)==62 and int(z.strict_positive_margin.sum())==x.positive_comparisons
check('Figure4 all 96 count records each retain 62 comparisons; 32 row box plotted points',len(counts)==96 and len(counts[counts.uncertainty_model=='row_box'])==32)
old=(REV/'work/render_supplement/v6/supplement.complete.md').read_text();new=(E/'supplement.complete.md').read_text()
def tables(text):
    return [x for x in re.findall(r'(?:^\|.*\n)+',text,re.M) if len(x.splitlines())>=2 and '---' in x.splitlines()[1]]
oldt=tables(old);newt=tables(new)
check('All 28 prior supplement table bodies byte identical to V6',oldt==newt[:28])
check('Legacy panel and coverage row counts 682 and 62',sum(len(t.splitlines())-2 for t in newt[4:26])==682 and sum(len(t.splitlines())-2 for t in newt[26:28])==62)
refs=(E/'work/literature/REFERENCES_NUMBERED.md').read_text().split('<!-- END NUMBERED BLOCK')[0]
refs=dict(re.findall(r'^\[(\d+)\] (.*?)(?=\n\n\[|\Z)',refs,re.M|re.S))
for name in ['main','supplement']:
    text=(E/f'{name}.complete.md').read_text();actual=dict(re.findall(r'^\[(\d+)\] (.*?)(?=\n\n\[|\Z)',text.split('# References',1)[1],re.M|re.S))
    check(name+' all 19 reference mappings exact',len(actual)==19 and all(actual[str(v)].strip()==refs[k].strip() for k,v in a['reference_mapping_old_to_current'].items()))
ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
mathdump={}
for kind,stem in [('main','Manuscript'),('supplement','Supplement')]:
    doc=E/f'work/render_{kind}/v3/NeuralFoil_Measurement_Correction_{stem}.docx';pin(doc)
    xml=ET.fromstring(zipfile.ZipFile(doc).read('word/document.xml'))
    displays=[p for p in xml.findall('.//w:p',ns) if p.find('m:oMath',ns) is not None and re.search(r'\((?:S)?\d+\)$',''.join(p.itertext()))]
    mathdump[kind]=[dict(number=i+1,text=''.join(x.itertext()),xml=ET.tostring(x,encoding='unicode')) for i,x in enumerate(displays)]
    check(kind+' native display count',len(displays)==(16 if kind=='main' else 28))
    md=(E/f'{kind}.complete.md').read_text()
    mathdump[kind+'_latex']=re.findall(r'\$\$(.*?)\$\$',md,re.S)
result=dict(status='PASS_NUMERIC_AND_SOURCE_CHECKS',checks=checks,input_sha256=pins,reference_mapping=a['reference_mapping_old_to_current'])
for name,data in [('CHECKS.json',result),('NATIVE_MATH.json',mathdump)]:
    dest=OUT/name;assert not dest.exists();dest.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(result['checks'],indent=2))
