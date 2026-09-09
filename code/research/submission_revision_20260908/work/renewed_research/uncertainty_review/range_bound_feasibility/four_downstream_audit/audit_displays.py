"""Independent saved presentation verification; no exporter import or arrays."""
import json,csv,io,hashlib
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
D=PROJECT/'submission_revision_20260908/renewed_manuscript_v9/additions/four_v9_displays';OUT=D/'attempt_1'
BINDING='50d47f6464353f485d9e74f28e212f5502ec11608334edcfc1d3dae54941765a'
LABELS=['qualified_four_D_harm_001','qualified_four_D_kl_harm_001']
REFS=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half','qualified_generic_harm_001','qualified_structural_harm_001','qualified_generic_kl_harm_001','qualified_structural_kl_harm_001','qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001']
NAMES=['Learned transfer policy','Established half strength','Proper-training core half','Qualified matched half','Generic H','Stage0 H','Generic KL','Stage0 KL','Paired-D H','Paired-D KL']
def rounding(x,places,signed=False):
    if isinstance(x,F):q=x;negative=x<0
    else:
        d=Decimal(x)
        if not d.is_finite():raise ValueError('finite decimal')
        q=F(d);negative=d.is_signed()
    n=round(abs(q)*10**places) # Fraction.__round__ uses exact nearest/even.
    sign='-' if negative else '+' if signed else ''
    return sign+str(n//10**places)+'.'+str(n%10**places).zfill(places)
def rows(raw):return list(csv.DictReader(io.StringIO(raw.decode())))
def main():
    pins={};checks=0
    def read(p,h=None):
        p=Path(p);assert not any(x.is_symlink() for x in (p,*p.parents));raw=p.read_bytes();s=hashlib.sha256(raw).hexdigest()
        if h is not None:assert h==s
        if str(p) in pins:assert pins[str(p)]==s
        pins[str(p)]=s;return raw
    manifest=json.loads(read(OUT/'MANIFEST.json'));assert manifest['status']=='COMPLETE' and manifest['config_sha256']==BINDING
    cfg=json.loads(read(HERE/'ROOT_FOUR_DISPLAY_BINDING.json',BINDING));assert cfg['export_authorized'] is True
    assert manifest['source_sha256']==cfg['source_sha256']
    for n,h in manifest['source_sha256'].items():read(D/n,h)
    for n,h in manifest['input_sha256'].items():read(ROOT/n,h)
    for n,h in manifest['output_sha256'].items():read(OUT/n,h)
    assert not (OUT/'FAILURE.json').exists()
    study=ROOT/'model_proposal/four_tree_matching_plan/downstream_plan';previous=cfg['certificate_replay_sha256']
    for phase in ['preflight','calibrate','score','assess']:
        binding=cfg['phases'][phase];r=json.loads(read(study/phase/'COMPLETE.json',binding['complete_sha256']));ap=json.loads(read(ROOT/binding['approval_path'],binding['approval_sha256']))
        assert r['status']=='COMPLETE' and r['summary']['predecessor_sha256']==previous and r['registry_sha256']==cfg['registry_sha256'] and r['approval_sha256']==binding['approval_sha256']
        assert ap['actual_execution_authorized'] is True and ap['predecessor_sha256']==previous
        audit=cfg['audits'][phase];qa=json.loads(read(ROOT/audit['path'],audit['sha256']));assert qa['status'].startswith('PASS') and audit['root_reviewed_pass'] is True
        previous=binding['complete_sha256']
    cal=json.loads(read(study/'calibrate/COMPLETE.json'));ass=json.loads(read(study/'assess/COMPLETE.json'));scalar=[]
    contexts=[f'group_{a}_fold_{i}' for a in (20260906,20260908) for i in range(5)]+['strict_source_'+s for s in ('stec8','vol1','vol2','vol3','all_uiuc_volumes')]+['final']
    for label in LABELS:
        for c in contexts:
            n=f'calibrator_{label}_{c}.json';raw=read(study/'calibrate'/n,cal['outputs'][n]);assert read(OUT/f'scalar_{label}_{c}.json')==raw;scalar.append(json.loads(raw,parse_float=Decimal));checks+=1
    assert json.loads(read(OUT/'scalar_records.json'),parse_float=Decimal)==scalar
    si={(s['candidate'],s['context']):s for s in scalar};tables={};full_cells=0
    for n,count in [('panel_metrics.csv',62),('bootstrap.csv',40),('candidate_summary.csv',2),('decisions.csv',2),('harm_metrics.csv',744)]:
        raw=read(study/'assess'/n,ass['outputs'][n]);assert read(OUT/('source_'+n))==raw
        selected=[r for r in rows(raw) if r['candidate'] in LABELS];assert rows(read(OUT/n))==selected and len(selected)==count
        tables[n]=selected;full_cells+=sum(len(r) for r in selected)
    panel_order=cfg['panel_order'];assert len(panel_order)==31
    pi={(r['candidate'],r['panel']):r for r in tables['panel_metrics.csv']};bi={(r['candidate'],r['reference'],r['assignment']):r for r in tables['bootstrap.csv']}
    f1=[]
    for c in contexts:
        h,k=(si[(l,c)] for l in LABELS);q=h['bound'];bound=F(int(q['numerator'],16),int(q['denominator'],16));assert k['bound']==q
        name=('A' if c.startswith('group_20260906_') else 'B')+' fold '+c[-1] if c.startswith('group_') else 'Final fit' if c=='final' else 'Holdout '+c[len('strict_source_'):].replace('all_uiuc_volumes','all UIUC')
        f1.append([name,rounding(bound,6),rounding(h['t'],6),rounding(k['t'],6),h['groups'],h['rows']])
    f2=[]
    for p in panel_order:
        title=p
        for old,new in [('history_20260906_','A '),('history_20260908_','B '),('strict_source_all_uiuc_volumes','Holdout all UIUC'),('strict_source_','Holdout '),('eligible_only/','Eligible '),('SG_exposed','SG'),('W_new_challenge','W'),('/',' '),('_',' ')]:title=title.replace(old,new)
        line=[title,pi[(LABELS[0],p)]['rows']]
        for l in LABELS:
            r=pi[(l,p)]
            for b in ['xlarge_CD','mean8_CD']:line.append(rounding(r[b+'_improvement_percent'],3,True)+' ('+r[b+'_worse_rows']+')')
        f2.append(line)
    f3=[]
    for l,ln in zip(LABELS,['Four-tree D H','Four-tree D KL']):
        for ref,rn in zip(REFS,NAMES):
            line=[ln,rn]
            for s in ['20260906','20260908']:
                r=bi[(l,ref,s)];assert r['draws']=='20000' and r['seed']=='2026090831'
                line.append(rounding(r['remaining_MAE_reduction_percent'],6,True)+' ['+rounding(r['conditional_95pct_lower'],6,True)+', '+rounding(r['conditional_95pct_upper'],6,True)+']')
            f3.append(line)
    expected={'F1':f1,'F2':f2,'F3':f3,'panel_order':panel_order,'reference_order':REFS};assert json.loads(read(OUT/'display_cells.json'))==expected
    md=read(OUT/'TABLES.md').decode();sections=md.split('Table F')[1:];assert len(sections)==3
    for sec,rr in zip(sections,[f1,f2,f3]):
        lines=[line for line in sec.splitlines() if line.startswith('|')][2:]
        assert [[x.strip() for x in line.strip('|').split('|')] for line in lines]==[[str(x) for x in r] for r in rr]
    display_cells=sum(len(r) for rr in (f1,f2,f3) for r in rr)
    for p,h in list(pins.items()):read(p,h)
    qa={'status':'PASS_INDEPENDENT_SAVED_DISPLAY','binding_sha256':BINDING,'manifest_sha256':pins[str(OUT/'MANIFEST.json')],'input_output_source_pins':pins,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scalar_objects_and_rawcopies':32,'selected_table_rows':{n:len(t) for n,t in tables.items()},'selected_fullprecision_cells':full_cells,'display_cells':display_cells,'display_rows':{'F1':16,'F2':31,'F3':20},'original_source_csv_byte_copies':5,'differences':[],'fits':0,'resampling':0,'rounding':'Independent Fraction conversion of decimal tokens and exact nearest-even integer rounding, including signed zero.'}
    dest=HERE/'FOUR_DISPLAY_QA.json'
    with dest.open('x') as f:json.dump(qa,f,indent=2)
    print(json.dumps({k:v for k,v in qa.items() if k!='input_output_source_pins'}))
if __name__=='__main__':main()
