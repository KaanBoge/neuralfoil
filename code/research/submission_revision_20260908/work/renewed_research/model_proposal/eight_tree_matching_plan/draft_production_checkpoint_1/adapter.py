"""Production-shape adapter, invoked only by separately approved phase wrapper.

Pure eight arithmetic plus pinned prior inventory/runtime. No import-time reads.
"""
import io
import zipfile
from fractions import Fraction as F

INVENTORY_SHA = 'a445462d5faf314ecbd7ea06cb45feb8c26cf99de8d05d246d026b4bbea4b40e'


def model_shape(raw, members):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        rows = z.infolist()
        if len(rows) != 7 or set(z.namelist()) != {k+'.npy' for k in members}:
            raise ValueError('exact seven safe model members')
        if any(x.is_dir() or x.flag_bits & 1 for x in rows):
            raise ValueError('encrypted/directory model member')
        expanded = sum(x.file_size for x in rows)
        if expanded > 4*2**20:
            raise MemoryError('4MiB model expansion admission')
        return expanded


def load_arrays(raw, members, model_sha, ledger):
    import numpy as np
    # model_shape must already have charged the expanded size before np.load.
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        arrays = {}
        for key in members:
            value = z[key]
            if value.dtype.hasobject:
                raise ValueError('no object model member')
            arrays[key] = value
            ledger.append(dict(operation='NPZ_materialization', member=key, model_sha256=model_sha,
                               dtype=str(value.dtype), shape=list(value.shape), bytes=int(value.nbytes)))
    return arrays


def construct(arrays, capsule, endpoint_chain, store, p, old, budget, accounting):
    """Caller established exact model and completed capsule provenance first."""
    if len(endpoint_chain) != 100:
        raise ValueError('old4complete chain')
    old.runtime()
    initial, paths, edges = old.inventory(arrays, budget)
    if initial.hex() != capsule['initial']:
        raise ValueError('common original initial value')
    current = F(initial), F(initial)
    store.begin()
    store.record(dict(kind='header', schema='EIGHT_TREE_MATCHING_JSONL_V1',
                      domain='FINITE_X62_V1', model_sha256=capsule['model_sha256'],
                      old4_certificate_sha256=capsule['certificate_sha256'],
                      old4_replay_complete_sha256=capsule['replay_complete_sha256'],
                      initial=initial.hex(), stages=400, blocks=50))
    for row in paths:
        budget.check()
        store.record(dict(kind='paths', **row))
    feasible = 0
    for j in range(50):
        budget.check()
        record, outgoing = p.block(paths[8*j:8*j+8], current, 8*(j+1),
                                   endpoint_chain[2*j+1], budget)
        feasible += sum(x['feasible'] for x in record['pairs'])
        store.record(record)
        current = outgoing
        del record
    old_final = endpoint_chain[-1]
    if not old_final[0] <= current[0] <= current[1] <= old_final[1]:
        raise ValueError('final old4nesting')
    def summary(bounds):
        return dict(lower=p.encode(bounds[0]), upper=p.encode(bounds[1]), B=p.encode(p.structural(bounds)))
    if summary(old_final) != capsule['final'] or p.structural(current) > p.structural(old_final):
        raise ValueError('unchanged structural conversion and nonloosening')
    counts = dict(stages=400, blocks=50, paths=sum(len(x['leaves']) for x in paths),
                  path_edges=edges, pair_classifications=budget.pairs, feasible_pairs=feasible)
    result = dict(kind='footer', counts=counts, original_four=summary(old_final), final=summary(current))
    store.record(result)
    store.finish_stream()
    return dict(counts=counts, original_four=result['original_four'], final=result['final'],
                accounting=accounting, old4_proof_inherited=True, model_materializations=1,
                features_targets_calibration_loaded=0, fits=0)
