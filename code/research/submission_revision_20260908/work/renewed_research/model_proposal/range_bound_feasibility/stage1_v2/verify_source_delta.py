"""Metadata/source-only identity witness: numerical bodies cannot change."""
import ast
import json
from pathlib import Path
import run_stage1 as r

OLD_PIN='4c80ebf2db6de68d856c4b26f83924730e087b3e36d289a8e0a92e4bab9ef397'
def main():
    old=r.HERE.parent/'stage1'
    frozen=r.json_checked(old/'IMPLEMENTATION_FREEZE.json',OLD_PIN)
    for name,h in frozen['source_sha256'].items():r.read_checked(old/name,h)
    unchanged=['numerics.py','evaluator.py','assess_stage1.py','test_stage1.py']
    records={}
    for name in unchanged:
        previous=(old/name).read_bytes();current=(r.HERE/name).read_bytes()
        if previous!=current:raise ValueError('unchanged source differs: '+name)
        records[name]={'byte_identical':True,'sha256':r.sha(current)}
    name='run_stage1.py'
    before=ast.parse((old/name).read_bytes());after=ast.parse((r.HERE/name).read_bytes())
    allowed={'encode','fraction','write_json'}
    def filtered(tree):
        return ast.dump(ast.Module(body=[x for x in tree.body if not
            (isinstance(x,ast.FunctionDef) and x.name in allowed)],type_ignores=[]),include_attributes=False)
    if filtered(before)!=filtered(after):raise ValueError('producer changed beyond codec/writer functions')
    records[name]={'allowed_changed_functions':sorted(allowed),'all_other_AST_identical':True,
                   'prior_sha256':r.sha((old/name).read_bytes()),'current_sha256':r.sha((r.HERE/name).read_bytes())}
    failures={name:r.sha((old/'results'/name).read_bytes()) for name in [
        'FAILURE.json','calibrator_qualified_structural_harm_001_group_20260906_fold_0.json']}
    expected={'FAILURE.json':'537dc2a14bd2c0602aebea8550a90c772a40e34f9f6dc3764afe6e238cc44f06',
        'calibrator_qualified_structural_harm_001_group_20260906_fold_0.json':'51ca8eca133f7aa5d389ff2663fc2e33eff6687c58e06fef160debd62a30fec7'}
    if failures!=expected:raise ValueError('original failure evidence changed')
    r.write_json(r.HERE/'SOURCE_DELTA.json',{'status':'SERIALIZATION_ONLY_NUMERICAL_AST_IDENTICAL',
        'prior_implementation_sha256':OLD_PIN,'sources':records,'preserved_failure_sha256':failures,
        'real_feature_parity_or_calibration_executed':False})
    print('Source delta and preserved v1 failure: PASS')

if __name__=='__main__':main()
