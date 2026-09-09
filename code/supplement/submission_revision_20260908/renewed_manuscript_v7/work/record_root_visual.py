"""Bind the root's explicitly enumerated actual page observations to bytes."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPORT = HERE / 'ROOT_VISUAL_REVIEW_20260908_1327.md'
OBSERVED = {
    ('main', 'v1'): [5, 6, 7, 8, 9, 10],
    ('main', 'v3'): [1, 11, 13, 19, 26, 27],
    ('main', 'v5'): [2, 3, 4],
    ('supplement', 'v5'): list(range(56, 68)),
    ('supplement', 'v7'): [1],
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    report_hash = sha(REPORT)
    for (kind, version), pages in OBSERVED.items():
        folder = HERE / ('render_' + kind) / version
        audit = json.loads((folder / 'LAYOUT_AUDIT.json').read_text())
        pdfs = list(folder.glob('*.pdf'))
        if len(pdfs) != 1 or sha(pdfs[0]) != audit['pdf_sha256']:
            raise ValueError('PDF differs from retained layout record')
        existing = {row['page']: row['png_sha256'] for row in audit['ledger']}
        rows = []
        for page in pages:
            digest = sha(folder / f'page-{page}.png')
            if digest != existing[page]:
                raise ValueError('Page differs from retained layout record')
            rows.append({'page': page, 'png_sha256': digest, 'result': 'PASS',
                         'individually_viewed_original_resolution': True})
        data = {'scope': 'Actual visual observations only; scientific scope correction remains separate',
                'pdf_sha256': audit['pdf_sha256'], 'report_sha256': report_hash,
                'kind': kind, 'version': version, 'pages': rows}
        dest = HERE / f'ROOT_PAGE_LEDGER_{kind}_{version}.json'
        with dest.open('x') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
        print(dest.name, sha(dest))

if __name__ == '__main__':
    main()
