import ast,hashlib,types
from fractions import Fraction as F
def production_root_adapter():
    tree = ast.parse(kl_raw)
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'upper_root')
    original = ast.dump(ast.Module(body=node.body[1:], type_ignores=[]), include_attributes=False)
    node.name = 'certified_upper_root'
    node.body[0] = ast.Expr(value=ast.Constant(
        'Production exact-q upper certificate; lower endpoint is for upward-q root only.'))
    adapted = ast.dump(ast.Module(body=node.body[1:], type_ignores=[]), include_attributes=False)
    if original != adapted:
        raise ValueError('root arithmetic AST changed')
    namespace = dict(kl.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<authenticated production KL root>', 'exec'), namespace)
    return namespace[node.name], hashlib.sha256(original.encode()).hexdigest()

def calibrate_kl_groups(group_means, bound):
    """Fixed beta=.05, tau=.01; exact bounded means, downward binary64 strength.

    No core fit. This function alone does not enforce a study's role/approval
    barrier. It accepts only exact values, never rounded display means.
    """
    bound = kl._rational(bound)
    values = [kl._rational(x) for x in group_means]
    if bound < 0 or any(not 0 <= x <= bound for x in values):
        raise ValueError('exact bounded means required')
    h = n.calibrate_exact_groups(values, bound)
    witness = None
    if bound == 0:
        upper = F(0)
        strength = 1.
        branch = 'zero_bound'
    elif not values:
        upper = bound
        strength = h['t']
        branch = 'no_groups_deterministic_bound'
    else:
        mean = sum(values, F(0))/len(values)
        root = certified_upper_root(mean/bound, len(values))
        # Both quantities bound the SAME exact KL endpoint. This is not a
        # minimum-of-arbitrary-confidence-intervals construction.
        kl_upper = bound*root['upper']
        upper = min(kl_upper, h['upper'])
        if not 0 < upper <= bound or upper < mean:
            raise ArithmeticError('mean or bounded-endpoint ordering failed')
        strength = n.q.directed(min(F(1), n.q.TAU/upper), False)
        witness = {
            'mean_exact': mean,
            'kl_upper_before_hoeffding_min': kl_upper,
            'root_at_upward_mean': root,
            'lower_endpoint_scope': 'root_at_q_upper_only',
            'upper_endpoint_scope': 'conservative_for_q_exact',
        }
        branch = 'bounded_iid_kl_with_certified_hoeffding_min'
    if not 0 <= n.q.rat(strength) <= 1 or n.q.rat(strength)*upper > n.q.TAU:
        raise ArithmeticError('downward risk budget failed')
    if upper > h['upper'] or n.q.rat(strength) < n.q.rat(h['t']):
        raise ArithmeticError('matched Hoeffding domination failed')
    return {
        'upper': upper, 't': strength, 'groups': len(values),
        'bound': bound, 'branch': branch,
        'matched_hoeffding_upper': h['upper'],
        'matched_hoeffding_t': h['t'],
        'root_witness': witness,
        'conditional_not_certified': True,
    }

def fit_kl_scalar(base, core, anchor, targets, identities, bound):
    """Production endpoint-loss calibration; external runner must enforce roles."""
    bound = kl._rational(bound)
    rows = len(base)
    if any(len(v) != rows for v in (core, anchor, targets, identities)):
        raise ValueError('aligned calibration vectors required')
    losses = [n.q.exact_endpoint_loss(b, c, h, y)
              for b, c, h, y in zip(base, core, anchor, targets)]
    means = n.group_means_exact(losses, identities, bound)
    result = calibrate_kl_groups(means.values(), bound)
    result.update(group_means=means, rows=rows,
                  exact_mean=sum(means.values(), F(0))/len(means) if means else None)
    return result

certified_upper_root,ROOT_AST=production_root_adapter()
