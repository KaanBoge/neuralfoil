"""Read-only scientific-input inventory of the user-provided starter ZIP.

No uploaded script or binary is executed. Nested archives are read in memory,
never extracted. Results are written only alongside this newly authored script.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
ARCHIVE = Path('/PATH_TO_YOUR_HOME/Downloads/NeuralFoil-export-starter-2026-09-06.zip')
PREFIX = 'NeuralFoil-export-starter-2026-09-06/'
SIZES = ['xxsmall', 'xsmall', 'small', 'medium', 'large', 'xlarge', 'xxlarge', 'xxxlarge']


def csv_rows(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    return reader.fieldnames, list(reader)


def main():
    with zipfile.ZipFile(ARCHIVE) as outer:
        def read(relative):
            return outer.read(PREFIX + relative)

        nf2_bytes = read('scratchpad/lsat/lsat-nf2.csv')
        columns, rows = csv_rows(nf2_bytes)
        expected = ['source', 'airfoil', 'config', 'geom_kind', 'Re', 'alpha',
                    'CL_meas', 'CD_meas', 'u_cd_span']
        expected += [f'{quantity}_{size}' for size in SIZES for quantity in ['CL', 'CD']]
        expected += ['conf_xlarge', 'tc', 'topxtr', 'botxtr', 'cm8']
        missing = sorted(set(expected) - set(columns))
        unexpected = sorted(set(columns) - set(expected))
        numeric = [c for c in expected if c not in ['source', 'airfoil', 'config', 'geom_kind']]
        invalid = {}
        for col in numeric:
            count = 0
            for row in rows:
                try:
                    count += not math.isfinite(float(row[col]))
                except (ValueError, TypeError, KeyError):
                    count += 1
            if count:
                invalid[col] = count
        nf_headers, nf_rows = csv_rows(read('scratchpad/lsat/lsat-nf.csv'))
        assert len(nf_rows) == len(rows), 'Extended/basic inference row counts differ'
        shared_mismatches = {col: sum(old.get(col) != new.get(col) for old, new in zip(nf_rows, rows))
                             for col in nf_headers}
        corpus_headers, corpus_rows = csv_rows(read('scratchpad/lsat/lsat-corpus.csv'))
        prior_nf_path = PROJECT / 'source/neuralfoil_repo/study/data/lsat-nf.csv'
        prior_columns, prior_rows = csv_rows(prior_nf_path.read_bytes())
        recovered_nf_bytes = read('scratchpad/lsat/lsat-nf.csv')

        nested = {}
        for name in ['volume01.zip', 'volume02.zip', 'volume03.zip', 'volume06.zip',
                     'Stec8.zip', 'coord_seligFmt.zip']:
            raw = read('scratchpad/lsat/' + name)
            z = zipfile.ZipFile(io.BytesIO(raw))
            infos = [x for x in z.infolist() if not x.is_dir()]
            assert sum(x.file_size for x in infos) < 100_000_000, 'Unexpectedly large nested archive'
            failed = z.testzip()
            assert failed is None, (name, failed)
            nested[name] = {'zip': z, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                            'files': len(infos), 'uncompressed_bytes': sum(x.file_size for x in infos),
                            'crc_verified': True}

        geometry = json.loads(read('scratchpad/lsat/lsat-geometry.json'))
        geom_rows = []
        for entry, meta in sorted(geometry.items()):
            path = meta['path'].replace('\\', '/')
            folders = path.lower().split('/')[:-1]
            if 'stec8' in folders:
                archive_name = 'Stec8.zip'
            elif 'coord_seligfmt' in folders:
                archive_name = 'coord_seligFmt.zip'
            else:
                raise ValueError(f'Unknown geometry path convention: {path}')
            z = nested[archive_name]['zip']
            basename = path.rsplit('/', 1)[-1]
            candidates = [n for n in z.namelist() if n.rsplit('/', 1)[-1] == basename]
            assert len(candidates) == 1, (entry, path, candidates)
            raw = z.read(candidates[0])
            points = []
            for line in raw.decode('utf-8-sig', errors='replace').splitlines():
                fields = line.split()
                if len(fields) != 2:
                    continue
                try:
                    xy = [float(x.replace('D', 'E').replace('d', 'e')) for x in fields]
                except ValueError:
                    continue
                if all(math.isfinite(x) for x in xy):
                    points.append(xy)
            geom_rows.append({'entry': entry, 'path': path, 'archive': archive_name,
                              'member': candidates[0], 'bytes': len(raw),
                              'finite_numeric_pairs': len(points), 'has_at_least_four_pairs': len(points) >= 4})

        result = {
            'status': 'Input availability/structure check only; not an aerodynamic validation or refit',
            'archive': str(ARCHIVE),
            'nf2': {'rows': len(rows), 'columns': len(columns), 'header': columns,
                    'missing_columns': missing, 'unexpected_columns': unexpected,
                    'invalid_numeric_counts': invalid,
                    'shared_field_mismatch_counts_vs_basic_inference': {k: v for k, v in shared_mismatches.items() if v},
                    'sha256': hashlib.sha256(nf2_bytes).hexdigest()},
            'basic_inference': {'rows': len(nf_rows), 'columns': len(nf_headers),
                                'matches_prior_parsed_headers': nf_headers == prior_columns,
                                'matches_prior_parsed_rows': nf_rows == prior_rows,
                                'matches_prior_bytes': recovered_nf_bytes == prior_nf_path.read_bytes(),
                                'matches_prior_after_crlf_normalization': recovered_nf_bytes.replace(b'\r\n', b'\n') == prior_nf_path.read_bytes().replace(b'\r\n', b'\n')},
            'raw_corpus': {'rows': len(corpus_rows), 'columns': len(corpus_headers)},
            'geometry': {'entries': len(geometry), 'all_paths_resolve_to_single_archive_member': True,
                         'entries_with_four_numeric_pairs': sum(x['has_at_least_four_pairs'] for x in geom_rows),
                         'insufficient_numeric_pairs': [x for x in geom_rows if not x['has_at_least_four_pairs']],
                         'caveat': 'Numeric-pair count is an availability screen, not geometry normalization or aerodynamic fidelity validation.'},
            'nested_archives': {n: {k: v for k, v in d.items() if k != 'zip'} for n, d in nested.items()},
            'environment_records_present': all(PREFIX + p in outer.namelist() for p in [
                'records/env/pip-freeze-nfenv.txt', 'records/env/python-version.txt',
                'records/env/xfoil/xfoil-binary-linux-x86_64',
                'records/env/xfoil/xfoil-6.99-source-original.tgz']),
            'uploaded_code_executed': False,
        }
        assert len(rows) == 13394 and len(columns) == 30 and not missing and not unexpected
        assert len(nf_rows) == 13394 and len(corpus_rows) == 14773 and len(geometry) == 203
        (OUT / 'recovered_input_inventory.json').write_text(json.dumps(result, indent=2) + '\n')
        with (OUT / 'geometry_archive_resolution.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(geom_rows[0]))
            writer.writeheader()
            writer.writerows(geom_rows)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
