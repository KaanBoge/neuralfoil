"""Finite source/payload authentication and exclusive durable outputs.

Source-only: real execution requires a separately pinned phase approval.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time
import types

CAP = 64*2**20
RESERVE = 2**20
LINE = 2**20


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    if type(value) != str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('exact SHA256')
    return value


def safe(path):
    p = Path(os.path.abspath(path))
    if any(ord(c) < 32 or ord(c) == 127 for c in str(p)):
        raise ValueError('control path')
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('symlink ancestor')
    return p


def read(path, expected, ledger, limit):
    p = safe(path)
    pin(expected)
    if not p.is_file() or p.stat().st_size > limit:
        raise ValueError('finite input limit')
    with p.open('rb') as f:
        raw = f.read(limit+1)
    if len(raw) > limit or sha(raw) != expected:
        raise ValueError('input bytes changed')
    ledger.append(dict(operation='authenticated_bytes', path=str(p), sha256=expected, bytes=len(raw)))
    return raw


def parse(raw, ledger, identity):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('duplicate key')
            result[k] = v
        return result
    result = json.loads(raw, object_pairs_hook=pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    ledger.append(dict(operation='JSON_parse', identity=identity, sha256=sha(raw), bytes=len(raw)))
    return result


def module(raw, expected, name, path):
    if sha(raw) != pin(expected):
        raise ValueError('executed source buffer')
    m = types.ModuleType(name)
    m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), m.__dict__)
    return m


def bounded_object(obj, depth=0, count=None):
    """Bound individual encoder tokens BEFORE JSONEncoder constructs them."""
    if count is None:
        count = [0]
    count[0] += 1
    if depth > 18 or count[0] > 30000:
        raise ValueError('output object admission')
    if type(obj) is dict:
        if len(obj) > 64 or any(type(k) != str or len(k) > 128 for k in obj):
            raise ValueError('output dictionary')
        for v in obj.values():
            bounded_object(v, depth+1, count)
    elif type(obj) in (list, tuple):
        if len(obj) > 1000:
            raise ValueError('output list')
        for v in obj:
            bounded_object(v, depth+1, count)
    elif type(obj) is str:
        if len(obj) > 16384:
            raise ValueError('output string')
    elif type(obj) is int:
        if obj.bit_length() > 64:
            raise ValueError('plain integer')
    elif type(obj) is float:
        if not math.isfinite(obj):
            raise ValueError('finite scalar')
    elif obj is not None and type(obj) is not bool:
        raise ValueError('output scalar type')


def line_bytes(obj):
    bounded_object(obj)
    buffer = bytearray()
    for token in json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                                  allow_nan=False).iterencode(obj):
        raw = token.encode('ascii')
        if len(buffer)+len(raw)+1 > LINE:
            raise MemoryError('1MiB line admission')
        buffer.extend(raw)
    buffer.append(10)
    return buffer


class Store:
    def __init__(self, path, deadline):
        self.path = safe(path)
        self.path.mkdir(exist_ok=False)
        self.deadline = deadline
        self.outputs = {}
        self.stream = None

    def used(self):
        total = 0
        for p in self.path.iterdir():
            if safe(p).is_dir() or not p.is_file():
                raise ValueError('flat outputs only')
            total += p.stat().st_size
        return total

    def check(self, extra=0, emergency=False):
        if self.used()+extra > CAP-(0 if emergency else RESERVE):
            raise OSError('64MiB logical cap')
        if not emergency and time.monotonic() >= self.deadline:
            raise TimeoutError('900second phase deadline')

    def json(self, name, obj, emergency=False):
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('output name')
        raw = line_bytes(obj)
        self.check(len(raw), emergency)
        p = safe(self.path/name)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(p, flags, 0o600), 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        self.outputs[name] = sha(raw)
        return self.outputs[name]

    def begin(self):
        self.check()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        self.stream = os.fdopen(os.open(safe(self.path/'certificate.jsonl'), flags, 0o600), 'wb')

    def record(self, obj):
        raw = line_bytes(obj)
        self.check(len(raw))
        self.stream.write(raw)
        self.stream.flush()

    def finish_stream(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.stream = None
        h = hashlib.sha256()
        with (self.path/'certificate.jsonl').open('rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                self.check()
                h.update(chunk)
        self.outputs['certificate.jsonl'] = h.hexdigest()

    def close_partial(self):
        if self.stream is not None:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()
            self.stream = None

    def reauthenticate(self, ledger):
        for name, expected in self.outputs.items():
            self.check()
            h = hashlib.sha256()
            with safe(self.path/name).open('rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    self.check()
                    h.update(chunk)
            if h.hexdigest() != expected:
                raise ValueError('accepted output changed')
            ledger.append(dict(operation='streamed_output_authentication', name=name, sha256=expected))
