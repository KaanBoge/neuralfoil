"""Independent table/scalar source reconciliation. No arrays or model imports."""
import csv,hashlib,io,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HERE=ROOT/'qualified_confidence_displays';OUT=HERE/'attempt_1'
METHODS=[('qualified_generic_harm_001','Generic H'),('qualified_structural_harm_001','Structural H'),
 ('qualified_generic_kl_harm_001','Generic KL'),('qualified_structural_kl_harm_001','Structural KL')]
ALL=[('unpenalized_transfer','Transfer reference'),('half_strength','Half reference')]+METHODS
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvread(p):return list(csv.DictReader(io.StringIO(p.read_text())))
def one(rows,**kw):
    found=[r for r in rows if all(r[k]==v for k,v in kw.items())]
    assert len(found)==1;return found[0]
def main():
    dest=Path(__file__).with_name('CONFIDENCE_DISPLAY_QA.json')
    if dest.exists():raise FileExistsError(dest)
    m=json.loads((OUT/'MANIFEST.json').read_text())
    assert m['source_sha256']==sha(HERE/'build_displays.py') and m['plan_sha256']==sha(HERE/'PLAN.md')
    for event in m['inputs']:assert sha(Path(event['path']))==event['sha256']
    for name,pin in m['output_sha256'].items():assert sha(OUT/name)==pin
    parent=ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1'
    addon=ROOT/'model_proposal/kl_bound_study/portable_plan/fresh_extraction_v1'
    for base,pin in ((parent,'3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'),
      (addon,'dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')):
        assert sha(base/'manifest.json')==pin
    summary=csvread(addon/'expected/candidate_summary.csv');panels=csvread(addon/'expected/panel_metrics.csv')
    count=0
    for outname,original,labels,n in [('complete_panels_186.csv','panel_metrics.csv',dict(ALL),186),
       ('complete_bootstrap_84.csv','bootstrap.csv',dict(ALL),84),('four_method_harms_1116.csv','harm_metrics.csv',dict(METHODS),1116)]:
        expected=[r for r in csvread(addon/'expected'/original) if r['candidate'] in labels]
        actual=csvread(OUT/outname);assert actual==expected and len(actual)==n
        count+=sum(len(row) for row in actual)
    scalars={};rows=csvread(OUT/'calibration_64.csv');assert len(rows)==64
    for row in rows:
        label,ctx=row['candidate'],row['context'];base=addon if '_kl_' in label else parent
        z=json.loads((base/f'scalars/{label}_{ctx}.json').read_text())
        assert z['context']==ctx and z['candidate' if base==addon else 'procedure']==label
        assert row['display']==dict(METHODS)[label] and row['rows']==str(z['rows']) and row['groups']==str(z['groups'])
        assert row['additional_t']==repr(z['t']) and row['nominal_total_strength']==repr((1+z['t'])/2)
        assert json.loads(row['bound_exact'])==z['bound'] and json.loads(row['upper_exact'])==z['upper']
        assert (label,ctx) not in scalars;scalars[label,ctx]=z
    actual=csvread(OUT/'six_method_summary.csv');assert len(actual)==6
    mainrows=[]
    for row,(label,display) in zip(actual,ALL):
        s=one(summary,candidate=label);a=one(panels,candidate=label,panel='W_new_challenge_w1015-20')
        e=one(panels,candidate=label,panel='eligible_only/W_new_challenge/w1015-20')
        assert (a['rows'],e['rows'])==('67','60')
        t=scalars[label,'final']['t'] if (label,'final') in scalars else None
        expected={'candidate':label,'display':display,'final_additional_t':'' if t is None else repr(t),
         'historical_A_xlarge_percent':s['20260906_xlarge_CD_improvement_percent'],
         'historical_B_xlarge_percent':s['20260908_xlarge_CD_improvement_percent'],
         'W1015_20_all_xlarge_percent':a['xlarge_CD_improvement_percent'],
         'W1015_20_eligible_xlarge_percent':e['xlarge_CD_improvement_percent']}
        assert row==expected
        mainrows.append([display,'N/A' if t is None else f'{t:.5f}',
         f"{float(expected['historical_A_xlarge_percent']):.4f} / {float(expected['historical_B_xlarge_percent']):.4f}",
         f"{float(a['xlarge_CD_improvement_percent']):.4f} / {float(e['xlarge_CD_improvement_percent']):.4f}"])
    def tabledata(p):return [[v.strip() for v in line.strip().strip('|').split('|')] for line in p.read_text().splitlines() if line.startswith('|')]
    assert tabledata(OUT/'main_table.md')[2:]==mainrows
    printed=tabledata(OUT/'supplement_tables.md');assert len(printed)==51
    contexts=sorted({ctx for label,ctx in scalars});assert len(contexts)==16
    for vals,ctx in zip(printed[2:18],contexts):
        z=[scalars[label,ctx] for label,_ in METHODS]
        name=ctx.replace('group_20260906_','A ').replace('group_20260908_','B ').replace('strict_source_','Holdout ')
        assert vals==[name,str(z[0]['groups']),str(z[0]['rows'])]+[f"{r['t']:.5f}" for r in z]
        assert len({(r['rows'],r['groups']) for r in z})==1
    views=[r['panel'] for r in panels if r['candidate']==METHODS[0][0]]
    for vals,view in zip(printed[20:],views):
        rr=[one(panels,candidate=label,panel=view) for label,_ in METHODS]
        name=view.replace('history_20260906','A').replace('history_20260908','B').replace('strict_source_','Holdout ').replace('eligible_only/','Eligible ').replace('W_new_challenge','W').replace('SG_exposed','SG').replace('_',' ')
        assert vals==[name,rr[0]['rows']]+[f"{float(r['mean8_CD_improvement_percent']):.3f} / {float(r['xlarge_CD_improvement_percent']):.3f}" for r in rr]
    assert len(views)==31 and len(set(views))==31
    d=csvread(addon/'expected/decisions.csv');assert len(d)==2
    assert all(r[k]=='False' for r in d for k in ('performance_advance','robustness_advance'))
    result={'status':'PASS_INDEPENDENT_DISPLAY_RECONCILIATION','scalar_rows':64,'panel_rows':186,
     'bootstrap_rows':84,'harm_rows':1116,'verbatim_table_fields_compared':count,'summary_rows':6,
     'printed_scalar_contexts':16,'printed_panel_views':31,'arrays_opened':False,
     'manifest_sha256':sha(OUT/'MANIFEST.json'),'outputs':m['output_sha256']}
    with dest.open('x') as f:json.dump(result,f,indent=2)
    print(result)
if __name__=='__main__':main()
