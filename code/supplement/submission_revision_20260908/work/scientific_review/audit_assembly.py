"""Read-only arithmetic and native-equation preservation checks of assembly."""
from pathlib import Path
import re,json,hashlib,zipfile
from lxml import etree
import pandas as pd
HERE=Path(__file__).resolve().parent;REV=HERE.parents[1];P=REV.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def panel_name(p):return p.replace('history_20260906','A').replace('history_20260908','B').replace('strict_source_','Holdout ').replace('W_new_challenge','W').replace('SG_exposed','SG').replace('eligible_only/','Eligible ').replace('_',' ').replace('/',' ')
def main():
    manifest=json.loads((REV/'work/ASSEMBLY.json').read_text())
    for n,h in manifest['source_sha256'].items():assert sha(P/n)==h,n
    texts={k:(REV/f'{k}.complete.md').read_text() for k in ['main','supplement']}
    for k,t in texts.items():assert sha(REV/f'{k}.complete.md')==manifest[k+'_sha256']
    for token in re.findall(r'`([0-9a-f]{50,80})`',texts['supplement']):assert len(token)==64,token
    # Every original main display equation and every independently authored proof display survives verbatim.
    md=(REV/'manuscript.md').read_text();theory=(HERE/'SUPPLEMENT_SECTIONS.md').read_text()
    displays=re.findall(r'\$\$(.*?)\$\$',md,re.S)
    for d in displays:assert '$$'+d+'$$' in texts['main']
    proof=re.findall(r'\\\[(.*?)\\\]',theory,re.S)
    for d in proof:assert '\\['+d+'\\]' in texts['supplement']
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'};mathstats={}
    for kind,name in [('main','Manuscript'),('supplement','Supplement')]:
        def xml(p):
            with zipfile.ZipFile(p) as z:return etree.fromstring(z.read('word/document.xml'))
        raw=xml(REV/f'work/render_{kind}/raw.docx');final=xml(REV/f'deliverables/NeuralFoil_Measurement_Correction_{name}.docx')
        a=[''.join(n.itertext()) for n in raw.xpath('//m:oMath',namespaces=ns)]
        b=[''.join(n.itertext()) for n in final.xpath('//m:oMath',namespaces=ns)]
        assert a==b,(kind,len(a),len(b));mathstats[kind]=len(a)
    pa=pd.read_csv(P/'model_development_20260907_cap_ablation/assessment/panel_metrics.csv')
    pb=pd.read_csv(P/'model_development_20260908_adaptive_scale/assessment/panel_metrics.csv')
    labels=list(pa.candidate.unique())+[x for x in pb.candidate.unique() if x not in set(pa.candidate)]
    merged=pd.concat([pa,pb[~pb.candidate.isin(pa.candidate)]])
    sections=re.split(r'^## Procedure \d+ ',texts['supplement'],flags=re.M)[1:];assert len(sections)==22
    checks=0
    for label,section in zip(labels,sections):
        if '# S8 ' in section:section=section.split('# S8 ')[0]
        rows=[l for l in section.splitlines() if l.startswith('| ')][2:]
        expected=merged[merged.candidate==label];assert len(rows)==len(expected)==31
        for line,(_,r) in zip(rows,expected.iterrows()):
            cells=[c.strip() for c in line.strip('|').split('|')]
            assert cells==[panel_name(r.panel),str(int(r.rows)),f'{r.mae_CD*1e4:.2f}',f'{r.xlarge_CD_improvement_percent:+.2f}',f'{r.mean8_CD_improvement_percent:+.2f}',f'{100*r.xlarge_CD_worse_fraction:.2f}'],(label,r.panel,cells)
            checks+=1
    cv=pd.read_csv(P/'model_development_20260908_adaptive_scale/assessment/coverage_metrics.csv');covchecks=0
    for method,number in [('fixed_mean8_scale',27),('adaptive_scale',28)]:
        section=texts['supplement'].split(f'Table S{number}.',1)[1].split('\n# ',1)[0].split('\n## ',1)[0]
        rows=[l for l in section.splitlines() if l.startswith('| ')][2:]
        for line,(_,r) in zip(rows,cv[cv.method==method].iterrows()):
            cells=[c.strip() for c in line.strip('|').split('|')]
            assert cells==[panel_name(r.panel),str(int(r.eligible_rows)),f'{100*r.eligible_row_coverage:.2f}',f'{int(r.fully_covered_bundles)}/{int(r.assessed_bundles)}',f'{r.median_interval_width_CD:.5f}',f'{r.p90_interval_width_CD:.5f}']
            covchecks+=1
    assert covchecks==62
    r=dict(status='PASS',main_display_equations_preserved=len(displays),proof_display_equations_preserved=len(proof),native_math_objects_preserved=mathstats,panel_table_rows=checks,coverage_table_rows=covchecks,assembly_sha256=sha(REV/'work/ASSEMBLY.json'),audit_sha256=sha(Path(__file__)))
    (HERE/'ASSEMBLY_AUDIT.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
if __name__=='__main__':main()
