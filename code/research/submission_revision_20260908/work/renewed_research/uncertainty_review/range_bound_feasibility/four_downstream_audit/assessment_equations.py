"""Authenticated independent review equations, never the producer assessor."""
import ast
from pathlib import Path
SOURCE=Path(__file__).resolve().parent.parent/'stage1_v2_audit/audit_metrics.py'
SHA='2af68f2c0e3adad5039952cd6aa9508111e6e01b05e940c4149741ad27681e90'
COUNTS={15:21,465:651,2790:3906,150:420,3255:7812}
def prepare(raw):
    """Only remove old I/O/return and update fixed cardinality assertions."""
    tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    assert len(fn.body)>3 and isinstance(fn.body[-1],ast.Return)
    assert [n.targets[0].id for n in fn.body[:2]]==['report','frames']
    fn.body=fn.body[2:];fn.body[-1]=ast.parse("return {'panels':panels,'decisions':decisions,'warnings':WARNINGS,'checks':COUNT}").body[0]
    replacements=[]
    class Fixed(ast.NodeTransformer):
        def visit_Assign(self,node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='labels':
                assert ast.unparse(node.value)=="report['candidates'] + report['controls']"
                node.value=ast.parse('list(table_labels)',mode='eval').body
            return self.generic_visit(node)
        def visit_Assert(self,node):
            # Restrict substitutions to old fixed count comparisons, not loss,
            # tolerance, bootstrap seed or arithmetic constants.
            for v in ast.walk(node.test):
                if isinstance(v,ast.Compare) and isinstance(v.left,ast.Call) and isinstance(v.left.func,ast.Name) and v.left.func.id=='len':
                    for c in v.comparators:
                        if isinstance(c,ast.Constant) and type(c.value) is int and c.value in COUNTS:
                            replacements.append(c.value);c.value=COUNTS[c.value]
            return node
    fn=Fixed().visit(fn)
    assert sorted(replacements)==sorted([15,465,2790,150,3255,465])
    eq=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='eq')
    return ast.fix_missing_locations(ast.Module(body=[eq,fn],type_ignores=[]))
def run(access,tables):
    import numpy as np
    import pandas as pd
    raw=access.read(SOURCE,SHA);tree=prepare(raw)
    ns={'np':np,'pd':pd,'frames':tables,'table_labels':list(tables['panel_metrics'].candidate.unique()),'COUNT':0,'WARNINGS':[]}
    exec(compile(tree,'<authenticated independent reviewer equations>','exec'),ns)
    result=ns['main']();panels=result['panels'];frame=tables['all_row_predictions'];eq=ns['eq']
    # The original reviewer equations cover all panel/group/harm/expected-harm,
    # bundle and bootstrap cells, plus decisions. Independently finish the two
    # descriptive tables added after that original source.
    for row in tables['intervention_metrics'].itertuples():
        part=frame[panels[row.panel]];y=part.measured_CD.to_numpy();p=part[row.candidate].to_numpy();anchor=part.qualified_matched_half.to_numpy();selected=abs(p-anchor)>1e-12;e=part[row.candidate+'__effective_fraction'].to_numpy()
        vals={'rows':len(part),'interventions':selected.sum(),'physical_eligible_rows':part.interval_applicable.sum(),'qualified_eligible_rows':part.qualified_gate.sum(),'intervention_fraction':selected.mean(),'effective_fraction_min':e.min(),'effective_fraction_mean':e.mean(),'effective_fraction_max':e.max()}
        for ref in ['qualified_matched_half','proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=abs(p-y)-abs(part[ref].to_numpy()-y)
            vals.update({ref+'__selected_harm_fraction':(d[selected]>1e-12).mean() if selected.any() else None,ref+'__selected_benefit_fraction':(d[selected]<-1e-12).mean() if selected.any() else None,ref+'__selected_positive_excess_CD':np.maximum(d[selected],0).mean() if selected.any() else None})
        for k,v in vals.items():eq(getattr(row,k),v)
    pm=tables['panel_metrics'];boot=tables['bootstrap'];groups=tables['group_metrics'];fields=['mean8_CD_improvement_percent','xlarge_CD_improvement_percent']
    for _,row in tables['candidate_summary'].iterrows():
        t=pm[pm.candidate.eq(row.candidate)]
        for k,v in {'minimum_all31_improvement_both_percent':t[fields].min().min(),'minimum_eligible8_improvement_both_percent':t[t.panel.str.startswith('eligible_only/')][fields].min().min(),'worst_strict_source_improvement_both_percent':t[t.panel.str.startswith('strict_source_')][fields].min().min()}.items():eq(row[k],v)
        for seed in [20260906,20260908]:
            s=t[t.panel.eq(f'history_{seed}_pooled')].iloc[0];g=groups[groups.assignment.eq(seed)&groups.candidate.eq(row.candidate)]
            for k in ['xlarge_CD_improvement_percent','mean8_CD_improvement_percent','mae_CD','median_absolute_error_CD','p90_absolute_error_CD']:eq(row[f'{seed}_{k}'],s[k])
            eq(row[f'{seed}_negative_identity_groups'],(g.xlarge_improvement_percent< -1e-6).sum());eq(row[f'{seed}_worst_group_improvement_percent'],g.xlarge_improvement_percent.min())
            for b in boot[boot.assignment.eq(seed)&boot.candidate.eq(row.candidate)].itertuples():eq(row[f'{seed}_remaining_MAE_reduction_vs_{b.reference}_percent'],b.remaining_MAE_reduction_percent)
    result['checks']=ns['COUNT'];return result
