"""Private two-runtime reproduction wrapper; no execution or data reads on import."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVES = {
    'feature_reproduction_private.zip': ('feature_reproduction', 'release_manifest.json'),
    'private_reproduction.zip': ('private_reproduction', 'manifest.json'),
}
COHORTS = {'historical': 8371, 'SG_exposed': 242, 'W_new_challenge': 255}
KEYS = ('X62', 'BASE_CD', 'XLARGE_CD', 'all_model_CD', 'alpha', 'Re')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative_name(name):
    p = PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and ':' not in name
            and str(p) == name and name != '.', 'Unsafe relative path: ' + name)
    return p


def authenticate_archive(path, expected_sha, prefix, manifest_name):
    require(sha(path) == expected_sha, 'Archive SHA256 mismatch: ' + str(path))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(set(names)) == len(names), 'Duplicate ZIP member')
        for item in z.infolist():
            p = relative_name(item.filename)
            require(p.parts[0] == prefix and len(p.parts) > 1, 'Unexpected archive root')
            require(not item.is_dir(), 'Unexpected directory member')
            require(not stat.S_ISLNK(item.external_attr >> 16), 'ZIP symlink forbidden')
        mpath = prefix + '/' + manifest_name
        manifest = json.loads(z.read(mpath))
        covered = {mpath}
        for name, digest in manifest['files'].items():
            relative_name(name)
            full = prefix + '/' + name
            require(sha_bytes(z.read(full)) == digest, 'Internal hash mismatch: ' + full)
            covered.add(full)
        require(covered == set(names), 'Unmanifested or missing archive member')
        return {'sha256': expected_sha, 'manifest_sha256': sha_bytes(z.read(mpath)),
                'files_checked': len(manifest['files']), 'archive_members': len(names)}


def verify_bundle(root=ROOT):
    root = Path(root)
    m = json.loads((root / 'manifest.json').read_text())
    for name, digest in m['files'].items():
        relative_name(name)
        require(sha(root / name) == digest, 'Bundle hash mismatch: ' + name)
    records = {}
    for name, (prefix, internal) in ARCHIVES.items():
        records[name] = authenticate_archive(root / 'archives' / name,
                                             m['files']['archives/' + name], prefix, internal)
    return {'status': 'PASS', 'mode': 'integrity_only', 'scientific_code_executed': False,
            'manifest_sha256': sha(root / 'manifest.json'), 'archives': records}


def new_directory(path):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), 'Output collision: ' + str(path))
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def extract_authenticated(root, out, verification):
    for name in ARCHIVES:
        path = root / 'archives' / name
        prefix, internal = ARCHIVES[name]
        authenticate_archive(path, verification['archives'][name]['sha256'], prefix, internal)
        with zipfile.ZipFile(path) as z:
            for item in z.infolist():
                target = out.joinpath(*PurePosixPath(item.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as dest:
                    dest.write(z.read(item))


def check_feature_parity(result):
    rows = result.get('comparisons', [])
    require(len(rows) == 55, 'Expected all 55 feature comparisons')
    ids = [(r['cohort'], r['stage'], r['key']) for r in rows]
    require(len(set(ids)) == 55 and {r['cohort'] for r in rows} == set(COHORTS),
            'Missing or duplicate comparison identities')
    for r in rows:
        require(r['unequal_elements'] == 0 and math.isfinite(r['max_abs_difference'])
                and r['max_abs_difference'] == 0, 'Feature mismatch: ' + repr(r))
    return {'comparisons': 55, 'unequal_elements': 0, 'status': 'PASS'}


def load_npz(source):
    import numpy as np
    with np.load(source, allow_pickle=False) as z:
        result = {k: z[k] for k in z.files}
    require(all(v.dtype.kind != 'O' for v in result.values()), 'Object dtype prohibited')
    return result


def check_arrays(generated, archived, n):
    import numpy as np
    for key in KEYS:
        a, b = generated[key], archived[key]
        shape = (n, 62) if key == 'X62' else ((n, 8) if key == 'all_model_CD' else (n,))
        require(a.shape == b.shape == shape, 'Bridge shape mismatch: ' + key)
        require(a.dtype == b.dtype == np.dtype('float64'), 'Bridge dtype mismatch: ' + key)
        require(np.isfinite(a).all() and np.isfinite(b).all(), 'Nonfinite bridge value: ' + key)
        require(np.array_equal(a, b), 'Bridge value mismatch: ' + key)


def verify_bridge(feature_results, root=ROOT):
    root = Path(root)
    result_dir = Path(feature_results)
    complete = json.loads((result_dir / 'complete.json').read_text())
    parity = check_feature_parity(complete)
    for name, digest in complete['outputs'].items():
        relative_name(name)
        require(sha(result_dir / name) == digest, 'Generated output hash mismatch: ' + name)
    records = []
    with zipfile.ZipFile(root / 'archives/private_reproduction.zip') as correction, \
            zipfile.ZipFile(root / 'archives/feature_reproduction_private.zip') as feature:
        for cohort, n in COHORTS.items():
            target = 'private_reproduction/data/' + cohort + '.npz'
            original = correction.read(target)
            archived = load_npz(io.BytesIO(original))
            generated = load_npz(result_dir / (cohort + '.npz'))
            feature_input = load_npz(io.BytesIO(feature.read('feature_reproduction/data/' + cohort + '.npz')))
            check_arrays(generated, archived, n)
            check_arrays(generated, feature_input, n)
            import numpy as np
            require(np.array_equal(feature_input['row_id'], np.arange(n)), 'Feature row order changed')
            if cohort == 'historical':
                for key in ['nf2_row_id', 'entry']:
                    require(np.array_equal(feature_input[key], archived[key]), 'Historical identity bridge: ' + key)
            records.append({'cohort': cohort, 'rows': n, 'keys_exact': list(KEYS),
                            'generated_sha256': sha(result_dir / (cohort + '.npz')),
                            'correction_input_sha256': sha_bytes(original)})
    return {'status': 'PASS', 'feature_parity': parity, 'cohorts': records,
            'boundary': 'Exact row-order equality; correction archive inputs remain unchanged'}


def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def reproduce(args, integrity):
    # No extraction or scientific execution occurs unless this mode is explicitly chosen.
    out = new_directory(args.output)
    transcript = []
    try:
        write_json(out / 'start.json', {'mode': 'reproduce', 'integrity': integrity,
                   'forward_python': str(args.forward_python), 'fit_python': str(args.fit_python),
                   'newly_provisioned_environment': False})
        extract_authenticated(ROOT, out, integrity)
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   PYTHONDONTWRITEBYTECODE='1', MPLCONFIGDIR=str(out / 'mpl'))
        env.pop('PYTHONOPTIMIZE', None)
        def execute(label, cmd):
            before = time.monotonic()
            with (out / (label + '.stdout.txt')).open('x') as stdout, \
                    (out / (label + '.stderr.txt')).open('x') as stderr:
                p = subprocess.run([str(v) for v in cmd], cwd=out, env=env, stdout=stdout, stderr=stderr)
            record = {'stage': label, 'command': [str(v) for v in cmd], 'returncode': p.returncode,
                      'seconds': time.monotonic() - before}
            transcript.append(record)
            require(p.returncode == 0, 'Subprocess failed; retain logs: ' + label)
        froot, croot = out / 'feature_reproduction', out / 'private_reproduction'
        execute('feature_tests', [args.forward_python, '-m', 'unittest', 'discover', '-s', froot, '-v'])
        execute('feature_generation', [args.forward_python, froot / 'regenerate_portable.py', '--output', out / 'feature_results'])
        # The forward runtime already contains the required NumPy; do not assume wrapper Python does.
        execute('feature_bridge', [args.forward_python, Path(__file__).resolve(), 'verify',
                                   '--feature-results', out / 'feature_results', '--report', out / 'bridge.json'])
        execute('correction_tests', [args.fit_python, '-m', 'unittest', 'discover', '-s', croot, '-v'])
        execute('correction_replay', [args.fit_python, croot / 'reproduce.py'])
        report = json.loads((croot / 'reproduced/report.json').read_text())
        expected = {'A_core_fits': 96, 'A_calibrators': 48, 'B_inner_core_fits': 48,
                    'B_scale_fits': 16, 'B_calibrators': 16, 'panels': 31, 'procedures': 22}
        require(all(report.get(k) == v for k, v in expected.items()), 'Correction count mismatch')
        require(report.get('status') == 'PASS' and report.get('native_array_parity') == 'exact'
                and report.get('calibrator_parity') == 'exact', 'Correction parity did not pass')
        verify_bundle()
        outputs = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
        write_json(out / 'complete.json', {'status': 'PASS', 'transcript': transcript, 'output_sha256': outputs,
                   'integrity': integrity, 'counts': expected, 'newly_provisioned_environment': False,
                   'scope': 'Exact numerical chain; archived correction inputs equal regenerated features; not independent validation'})
    except BaseException as error:
        write_json(out / 'failure.json', {'status': 'FAIL', 'error_type': type(error).__name__,
                   'error': str(error), 'transcript': transcript})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    v = sub.add_parser('verify', help='Read-only integrity, optionally exact generated-feature bridge')
    v.add_argument('--feature-results', type=Path)
    v.add_argument('--report', type=Path, help='Optional new report; existing paths refused')
    r = sub.add_parser('reproduce', help='Explicit forward generation and 160-fit replay in a new directory')
    r.add_argument('--output', type=Path, required=True)
    r.add_argument('--forward-python', type=Path, required=True)
    r.add_argument('--fit-python', type=Path, required=True)
    args = p.parse_args()
    require(not sys.flags.optimize, 'Run without Python -O')
    integrity = verify_bundle()
    if args.mode == 'verify':
        if args.feature_results:
            integrity['bridge'] = verify_bridge(args.feature_results)
        if args.report:
            write_json(args.report, integrity)
        print(json.dumps(integrity, indent=2))
    else:
        for interpreter in [args.forward_python, args.fit_python]:
            require(interpreter.is_absolute() and interpreter.is_file(), 'Use an existing absolute interpreter path')
        reproduce(args, integrity)


if __name__ == '__main__':
    main()
