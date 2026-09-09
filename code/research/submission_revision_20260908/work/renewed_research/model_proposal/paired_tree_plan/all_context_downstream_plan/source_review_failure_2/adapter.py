"""Successor paths/storage and separate inherited-registry authentication."""
import datetime
import json
import os
import signal
import sys
import time
from pathlib import Path
import legacy_adapter as old
import storage

HERE = Path(__file__).resolve().parent
ROOT = old.ROOT
CONTEXTS = old.CONTEXTS
REGISTRY_NAME = 'REGISTRY.json'
LEGACY_SHA = '0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a'
PRODUCER_SHA = '0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd'
PHASES = ('preflight', 'calibrate', 'score', 'assess')
sha, read, parse, json_read, safe, now = old.sha, old.read, old.parse, old.json_read, old.safe, old.now
_bound = None
_budget = None


def roots():
    return [old.HERE / p for p in old.PHASE_DIRS] + [HERE / p for p in PHASES] + [HERE / 'execution_evidence']


def bind(reg, pin, boot_pins):
    global _bound
    if _bound is not None:
        raise ValueError('one phase per process')
    if reg['inherited']['registry_sha256'] != LEGACY_SHA or reg['inherited']['producer_sha256'] != PRODUCER_SHA:
        raise ValueError('inherited identities')
    if reg['output_roots'] != [str(p.relative_to(ROOT)) for p in roots()]:
        raise ValueError('finite output roots')
    if reg['contexts'] != CONTEXTS or reg['phases'] != list(PHASES):
        raise ValueError('fixed contexts/phases')
    if reg['logical_cap'] != storage.CAP or reg['failure_reserve'] != storage.RESERVE:
        raise ValueError('unchanged cumulative limit')
    for k in ('replay_sha256', 'producer_approval_sha256', 'replay_approval_sha256'):
        h = reg['inherited'][k]
        if not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
            raise ValueError('missing frozen inherited receipt/approval')
    for name in ('producer_approval_path', 'replay_approval_path'):
        p = Path(reg['inherited'][name])
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('relative inherited approval path')
    for name in reg['external_sources']:
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('relative external source path')
    _bound = reg, pin, dict(boot_pins)


def authenticate(reg, pin, approval, approval_sha, phase, ledger):
    if _bound is None or _bound[1] != pin or _bound[0] != reg:
        raise ValueError('bootstrap binding required')
    read(HERE / REGISTRY_NAME, pin, ledger)
    for path, h in _bound[2].items():
        read(path, h, ledger, 'executed source buffer reauthentication')
    for name, h in reg['external_sources'].items():
        read(ROOT / name, h, ledger, 'external source authentication')
    ap = json_read(approval, approval_sha, ledger)
    expected = dict(registry_sha256=pin, phase=phase, seconds=900, workers=1,
                    actual_execution_authorized=True, output=str((HERE / phase).relative_to(ROOT)),
                    runtime=str(Path(sys.executable).absolute()), contexts=CONTEXTS,
                    output_roots=reg['output_roots'], logical_cap=storage.CAP,
                    failure_reserve=storage.RESERVE, inherited_certificate_registry_sha256=LEGACY_SHA)
    if set(ap) != set(expected) | {'predecessor_sha256'}:
        raise ValueError('strict approval fields')
    if any(type(ap[k]) is not type(v) or ap[k] != v for k, v in expected.items()):
        raise ValueError('strict downstream approval')
    if phase not in PHASES or any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS')):
        raise ValueError('phase/thread limit')
    # Always authenticate inherited complete barrier before archive byte/array access.
    certificate_chain('certificates_replay', reg['inherited']['replay_sha256'], pin, ledger)
    return ap


def certificate_chain(phase, pin, downstream_sha, ledger):
    if _bound is None or downstream_sha != _bound[1] or phase != 'certificates_replay':
        raise ValueError('dual-registry boundary')
    inherited = _bound[0]['inherited']
    if pin != inherited['replay_sha256']:
        raise ValueError('inherited replay predecessor')
    reg = json_read(old.HERE / 'REGISTRY_v3.json', LEGACY_SHA, ledger)
    for name, h in reg['sources'].items():
        read(old.HERE / name, h, ledger, 'inherited source authentication')
    for name, h in reg['external_sources'].items():
        read(ROOT / name, h, ledger, 'inherited dependency authentication')
    for ph, key in [('certificates_produce', 'producer'), ('certificates_replay', 'replay')]:
        ap_path = ROOT / inherited[key + '_approval_path']
        ap = old.authenticate(reg, LEGACY_SHA, ap_path, inherited[key + '_approval_sha256'], ph, ledger)
        record = json_read(old.HERE / ph / 'COMPLETE.json', inherited[key + '_sha256'], ledger)
        if record['approval_sha256'] != inherited[key + '_approval_sha256']:
            raise ValueError('aggregate approval binding')
        if ph == 'certificates_replay' and (ap['predecessor_sha256'] != PRODUCER_SHA or record['summary']['predecessor_sha256'] != PRODUCER_SHA):
            raise ValueError('replay/producer binding')
        for ctx in CONTEXTS[:-1]:
            entry = record['summary']['contexts'][ctx]
            child = json_read(old.HERE / ph / ctx / 'COMPLETE.json', entry['complete_sha256'], ledger)
            if child['approval_sha256'] != inherited[key + '_approval_sha256']:
                raise ValueError('child approval binding')
    return old.certificate_chain(phase, pin, LEGACY_SHA, ledger)


def names(phase):
    result = {'ATTEMPT.json', 'ACCESS.json', 'COMPLETE.pending.json', 'COMPLETE.json', 'FAILURE.json'}
    labels = ['qualified_paired_D_harm_001', 'qualified_paired_D_kl_harm_001']
    if phase == 'preflight':
        result.add('REFERENCE_PASS.json')
    elif phase == 'calibrate':
        result.update('membership_' + c + '.json' for c in CONTEXTS)
        result.update(f'calibrator_{label}_{c}.json' for label in labels for c in CONTEXTS)
    elif phase == 'score':
        native = CONTEXTS + ['SG_exposed', 'W_new_challenge']
        result.update('inference_' + c + '.npz' for c in native)
        result.update('predictions_' + c + '.csv' for c in native if c != 'final')
    elif phase == 'assess':
        result.update({'OLD_FLOAT_DIFFERENCES.json', 'PARITY.json'})
        result.update(n + '.csv' for n in ('panel_metrics', 'bootstrap', 'group_metrics', 'harm_metrics',
                      'decisions', 'candidate_summary', 'expected_harm_metrics', 'bundle_harm_metrics',
                      'intervention_metrics', 'all_row_predictions'))
    else:
        raise ValueError('phase')
    return result


def save(path, obj):
    return _budget.json(path, obj)


def scalar(path, obj, codec):
    return _budget.scalar(path, obj, codec)


def npz(path, arrays):
    return _budget.npz(path, arrays)


def csv(path, frame):
    return _budget.csv(path, frame)


def attempt(out, meta, work, seconds=900):
    global _budget
    if _bound is None or seconds != 900 or safe(out) != HERE / meta['phase']:
        raise ValueError('approved fixed attempt required')
    out = safe(out)
    if out.exists():
        raise FileExistsError(out)
    _budget = storage.Budget(roots(), out, names(meta['phase']))
    _budget.check()
    out.mkdir(exist_ok=False)
    start = time.monotonic()
    ledger, outputs = [], {}
    meta = dict(meta, start_utc=now(), inherited_certificate_registry_sha256=LEGACY_SHA)
    previous = signal.getsignal(signal.SIGALRM)
    term = signal.getsignal(signal.SIGTERM)
    def timeout(*unused):
        raise TimeoutError('fixed phase deadline')
    signal.signal(signal.SIGALRM, timeout)
    signal.signal(signal.SIGTERM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        outputs['ATTEMPT.json'] = save(out / 'ATTEMPT.json', meta)
        summary = work(out, ledger, outputs, start + seconds)
        outputs['ACCESS.json'] = save(out / 'ACCESS.json', ledger)
        _budget.verify()
        result = dict(meta, status='COMPLETE', finish_utc=now(), seconds=time.monotonic() - start,
                      outputs=outputs, summary=summary, cumulative_bytes_before_complete=_budget.usage())
        # Serialize/fsync and verify a candidate before making any COMPLETE name visible.
        # Keep the candidate hardlink as evidence and charge both logical paths.
        save(out / 'COMPLETE.pending.json', result)
        _budget.verify()
        target = _budget.target(out / 'COMPLETE.json')
        _budget.check((out / 'COMPLETE.pending.json').stat().st_size)
        if time.monotonic() >= start + seconds:
            raise TimeoutError('deadline before receipt publication')
        os.link(out / 'COMPLETE.pending.json', target)
        # No fallible post-publication checks: this is the commit point.
        return result
    except BaseException as exc:
        # No unbounded ledger/error repr is serialized on the emergency path.
        if not (out / 'FAILURE.json').exists():
            try:
                _budget.json(out / 'FAILURE.json', storage.failure_payload(meta, exc, outputs, ledger), emergency=True)
            except BaseException:
                # Preserve the original failure; OS/interrupt failures can prevent a durable note.
                # Existing partial files remain. Never manufacture a successful receipt.
                pass
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        signal.signal(signal.SIGTERM, term)
        _budget = None
