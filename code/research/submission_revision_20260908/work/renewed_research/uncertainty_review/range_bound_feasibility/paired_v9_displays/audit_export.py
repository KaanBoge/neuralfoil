"""Independent string/JSON/display reconciliation; no producer import."""
import csv,io,json,hashlib
from pathlib import Path
from fractions import Fraction
HERE=Path(__file__).resolve().parent;D=HERE/'attempt_1';ROOT=HERE.parents[2];S=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
H='qualified_paired_D_harm_001';K='qualified_paired_D_kl_harm_001';LABELS={H,K};checks=0;pins=[]
def eq(a,b):
    global checks
    assert type(a)==type(b) and a==b,(a,b);checks+=1
def read(p,h):
    raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==h;pins.append({'path':str(p),'sha256':h});return raw
def rows(raw):return list(csv.DictReader(io.StringIO(raw.decode())))
def main():
    out=HERE/'EXPORT_AUDIT_QA.json'
    if out.exists():raise FileExistsError('preserve audit')
    manifest=json.loads(read(D/'MANIFEST.json','6b64d75940b6489360b98331015fadbeccce4a5fd59835b271531e71823a2486'))
    inp={p:read(Path(p),h) for p,h in manifest['input_sha256'].items()};exp={n:read(D/n,h) for n,h in manifest['output_sha256'].items()}
    for n,h in manifest['source_sha256'].items():read(HERE/n,h)
    full={};cellcounts={}
    for n in ('panel_metrics.csv','bootstrap.csv','candidate_summary.csv','decisions.csv','harm_metrics.csv'):
        a=[v for v in rows(inp[str(S/'assess'/n)]) if v['candidate'] in LABELS];b=rows(exp[n]);eq(len(a),len(b));full[n]=a
        for x,y in zip(a,b):
            eq(list(x),list(y))
            for k in x:eq(x[k],y[k])
        cellcounts[n]=sum(map(len,a))
    original=[]
    for p,b in inp.items():
        if Path(p).name.startswith('calibrator_'):original.append(json.loads(b))
    original={(v['candidate'],v['context']):v for v in original};saved=json.loads(exp['scalar_records.json']);eq(len(saved),32)
    for v in saved:eq(v,original[(v['candidate'],v['context'])])
    sf=rows(exp['scalars.csv']);eq(len(sf),32)
    for v in sf:
        o=original[(v['candidate'],v['context'])];f=Fraction(int(o['bound']['numerator'],16),int(o['bound']['denominator'],16))
        want={'context':o['context'],'candidate':o['candidate'],'bound':repr(float(f)),'t':repr(o['t']),'groups':str(o['groups']),'rows':str(o['rows']),'bound_exact_json':json.dumps(o['bound'],sort_keys=True),'upper_exact_json':json.dumps(o['upper'],sort_keys=True),'exact_mean_json':json.dumps(o['exact_mean'],sort_keys=True)}
        eq(set(v),set(want))
        for k in want:eq(v[k],want[k])
    displays=json.loads(exp['display_cells.json']);p1,p2,p3=[displays[k] for k in ('P1','P2','P3')];eq([len(p1),len(p2),len(p3)],[16,31,18]);eq([len(r) for r in p1],[6]*16);eq([len(r) for r in p2],[6]*31);eq([len(r) for r in p3],[4]*18)
    contexts=[v['context'] for v in saved if v['candidate']==H]
    for c,line in zip(contexts,p1):
        h,k=original[(H,c)],original[(K,c)];f=Fraction(int(h['bound']['numerator'],16),int(h['bound']['denominator'],16))
        label=(('A' if '20260906' in c else 'B')+' fold '+c.rsplit('_',1)[1]) if c.startswith('group_') else c.replace('strict_source_','Leave out ').replace('all_uiuc_volumes','all UIUC').replace('final','Final fit')
        for a,b in zip(line,[label,f'{float(f):.6f}',f"{h['t']:.6f}",f"{k['t']:.6f}",h['groups'],h['rows']]):eq(a,b)
    pm={(v['candidate'],v['panel']):v for v in full['panel_metrics.csv']}
    for panel,line in zip(displays['panel_order'],p2):
        h,k=pm[(H,panel)],pm[(K,panel)];eq(line[0],panel.replace('history_20260906_','A: ').replace('history_20260908_','B: ').replace('strict_source_','Leave out ').replace('_',' '));eq(line[1],h['rows'])
        want=[f"{float(v[b+'_improvement_percent']):+.3f} ({v[b+'_worse_rows']})" for v in (h,k) for b in ('xlarge_CD','mean8_CD')]
        for a,b in zip(line[2:],want):eq(a,b)
    bm={(v['candidate'],v['reference'],v['assignment']):v for v in full['bootstrap.csv']};i=0
    for c in (H,K):
        for ref in displays['reference_order']:
            line=p3[i];i+=1;eq(line[0],displays['candidate_labels'][c]);eq(line[1],displays['candidate_labels'][ref])
            for a,cell in zip(('20260906','20260908'),line[2:]):
                v=bm[(c,ref,a)];eq(cell,f"{float(v['remaining_MAE_reduction_percent']):+.6f} [{float(v['conditional_95pct_lower']):+.6f}, {float(v['conditional_95pct_upper']):+.6f}]")
    text=exp['TABLES.md'].decode()
    for table in (p1,p2,p3):
        for r in table:eq(text.count('| '+' | '.join(map(str,r))+' |'),1)
    result={'status':'PASS_ALL_EXPORTED_FIELDS','manifest_sha256':'6b64d75940b6489360b98331015fadbeccce4a5fd59835b271531e71823a2486','full_precision_source_csv_cells':cellcounts,'scalar_csv_cells':32*9,'complete_scalar_objects':32,'display_cells':16*6+31*6+18*4,'comparisons':checks,'hash_checks':len(pins),'pins':pins,'resampling':0,'reassessment':0,'array_access':0,'differences':[]}
    with out.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='pins'}));print('QA_SHA256='+hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
