"""Production exact-group calibration; frozen Stage0 arithmetic authenticated by AST.

Real data may be passed only after an externally approved parity barrier.
Import authenticates source code only; no data is read or calibration performed.
"""
import ast
import hashlib
from pathlib import Path
import types

PIN = '76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'
SOURCE = Path(__file__).resolve().parents[1]/'qualified_numerics.py'
raw = SOURCE.read_bytes()
if hashlib.sha256(raw).hexdigest() != PIN:
    raise ValueError('Stage0 numerical source authentication failed')
q = types.ModuleType('authenticated_qualified_stage0')
exec(compile(raw, str(SOURCE), 'exec'), q.__dict__)


def production_equivalent(old_name, new_name, doc):
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == old_name)
    original = ast.dump(ast.Module(body=node.body[1:], type_ignores=[]), include_attributes=False)
    node.name = new_name
    node.body[0] = ast.Expr(value=ast.Constant(doc))
    converted = ast.dump(ast.Module(body=node.body[1:], type_ignores=[]), include_attributes=False)
    if original != converted:
        raise ValueError('production arithmetic AST changed')
    namespace = dict(q.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<authenticated production equivalent>', 'exec'), namespace)
    return namespace[new_name], hashlib.sha256(original.encode()).hexdigest()


group_means_exact, GROUP_AST = production_equivalent(
    'exact_group_means', 'group_means_exact',
    'Production exact means; real inputs require completed approved parity barrier.')
calibrate_exact_groups, CONFIDENCE_AST = production_equivalent(
    'synthetic_confidence', 'calibrate_exact_groups',
    'Production conservative calibration; real inputs require completed approved parity barrier.')


def fit_scalar(base, core, anchor, targets, identities, bound):
    """No fitting of a core. Strictly bounded exact endpoint-loss scalar calibration."""
    n = len(base)
    if any(len(v) != n for v in [core, anchor, targets, identities]):
        raise ValueError('aligned calibration vectors required')
    losses = [q.exact_endpoint_loss(b,c,h,y) for b,c,h,y in zip(base,core,anchor,targets)]
    means = group_means_exact(losses, identities, bound)
    result = calibrate_exact_groups(means.values(), bound)
    result.update(bound=bound, group_means=means, rows=n,
                  exact_mean=sum(means.values(),q.F(0))/len(means) if means else None)
    return result


def predictions(model, base, core, anchor, gate):
    import numpy as np
    t = model['t']
    if not 0 <= q.rat(t) <= 1:
        raise ValueError('invalid strength')
    p = np.array([q.inward_predict(h,c,t) if g else b
                  for b,c,h,g in zip(base,core,anchor,gate)])
    effective = np.array([float((q.rat(v)-q.rat(h))/(q.rat(c)-q.rat(h)))
                          if g and c != h else 0.
                          for v,h,c,g in zip(p,anchor,core,gate)])
    return p, effective
