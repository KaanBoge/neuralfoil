"""Exact-source bootstrap. Registry cannot be frozen until replay barrier exists."""
import argparse
import contextlib
import hashlib
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / 'all_context_plan'
OLD_REGISTRY = '0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a'
OLD_ADAPTER = 'f76393b6d6cac459a04051551936624646dbf24adae00262eb67720cc0a90e82'
OLD_INPUTS = '4d0915bdbeb0ed4d10f1618f3c98e5962d21edbd7bcbd6fa492f4da07c9ca194'
LOCAL = ('run.py', 'storage.py', 'adapter.py', 'study.py')


def raw(path, pin):
    p = Path(path).absolute()
    if any(x.is_symlink() for x in (p, *p.parents)) or p.stat().st_size > 128 * 2**20:
        raise ValueError('source path/size')
    b = p.read_bytes()
    if hashlib.sha256(b).hexdigest() != pin:
        raise ValueError('source hash')
    return b


@contextlib.contextmanager
def loaded(buffers):
    old = {name: sys.modules.get(name) for name in buffers}
    result = {}
    try:
        for name, (path, b) in buffers.items():
            m = types.ModuleType(name)
            m.__file__ = str(path)
            sys.modules[name] = m
            exec(compile(b, str(path), 'exec'), m.__dict__)
            result[name] = m
        yield result
    finally:
        for name, m in old.items():
            if m is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = m


def execute(args):
    # No source import or scientific member parsing before complete source authentication.
    reg = json.loads(raw(HERE / 'REGISTRY.json', args.registry_sha256))
    if reg['entrypoint_sha256'] != args.entry_sha256:
        raise ValueError('entrypoint pin')
    pins = {HERE / name: reg['sources'][name] for name in LOCAL}
    pins[HERE / 'run.py'] = args.entry_sha256
    pins.update({LEGACY / 'adapter.py': OLD_ADAPTER, LEGACY / 'study_inputs.py': OLD_INPUTS,
                 LEGACY / 'REGISTRY_v3.json': OLD_REGISTRY})
    for name, pin in reg['sources'].items():
        if Path(name).name != name:
            raise ValueError('finite local source path')
        pins[HERE / name] = pin
    for name, pin in reg['provenance'].items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('finite provenance path')
        pins[HERE / p] = pin
    if pins[HERE / 'run.py'] != args.entry_sha256:
        raise ValueError('registry entry identity')
    buffers = {p: raw(p, h) for p, h in pins.items()}
    with loaded({name: (p, buffers[p]) for name, p in [
        ('legacy_adapter', LEGACY / 'adapter.py'), ('storage', HERE / 'storage.py'),
        ('adapter', HERE / 'adapter.py'), ('study_inputs', LEGACY / 'study_inputs.py'),
        ('downstream_study', HERE / 'study.py')]
    }) as ms:
        a = ms['adapter']
        a.bind(reg, args.registry_sha256, pins)
        # Approval and full inherited barrier precede even attempt-directory creation.
        a.authenticate(reg, args.registry_sha256, args.approval, args.approval_sha256, args.phase, [])
        result = ms['downstream_study'].execute(args)
        return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['preflight', 'calibrate', 'score', 'assess'])
    for key in ('registry-sha256', 'entry-sha256', 'approval', 'approval-sha256'):
        p.add_argument('--' + key, required=True)
    # No unbounded stdout receipt/log. Authoritative receipt is in the guarded phase directory.
    try:
        execute(p.parse_args())
    except BaseException as exc:
        # Parent may capture this bounded status only in its registered evidence path.
        sys.stderr.write('FAILED_STOP_NO_RETRY: ' + type(exc).__name__[:128] + '\n')
        sys.exit(1)
