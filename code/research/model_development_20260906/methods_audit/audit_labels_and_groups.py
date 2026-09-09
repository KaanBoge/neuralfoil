"""Read-only cohort/key/group audit; no model training or uploaded-code execution."""
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
BASE = ROOT / 'validation_extension/export_intake_20260906/payload_n805d74v/NeuralFoil-export-starter-2026-09-06/scratchpad/lsat'
OUT = Path(__file__).resolve().parent


def rows(name):
    with (BASE / name).open(newline='') as f:
        return list(csv.DictReader(f))


def condition(r):
    return r['source'], r['airfoil'], round(float(r['Re'])), round(float(r['alpha']), 2)


def measurement(r, predicted=False):
    return (r['source'], r['airfoil'], round(float(r['Re']), 3), round(float(r['alpha']), 4),
            round(float(r['CL_meas' if predicted else 'CL']), 5), round(float(r['CD_meas' if predicted else 'CD']), 6))


def write_csv(name, data, fields=None):
    if fields is None:
        fields = list(data[0])
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(data)


def nominal(entry):
    """Conservative split grouping, not a claim of identical physical models.

    Parenthetical builder labels are removed for all sources. Explicit SoarTech
    A/B/C/D profiler variants and neutral F0 labels are pooled by nominal name.
    No generic trailing-letter removal is performed (e.g. Goe 417a is retained).
    """
    _, name = entry.split('|', 1)
    clean = re.sub(r'\([^)]*\)', '', name).strip()
    clean = re.sub(r'\bF0\b', '', clean, flags=re.I)
    token = re.sub(r'[^a-z0-9]', '', clean.lower())
    aliases = {
        'e205a':'e205', 'e205b':'e205', 'e214a':'e214', 'e214b':'e214', 'e214c':'e214',
        'e374a':'e374', 'e374b':'e374', 'e387a':'e387', 'e387b':'e387',
        'fx63137a':'fx63137', 'fx63137b':'fx63137', 'hq29a':'hq29', 'hq29b':'hq29',
        's2091a':'s2091', 's2091b':'s2091', 's3021a':'s3021', 's3021b':'s3021',
        's4061a':'s4061', 's4061b':'s4061', 'sd7032b':'sd7032', 'sd7032c':'sd7032', 'sd7032d':'sd7032',
    }
    return aliases.get(token, token)


raw, nf = rows('lsat-corpus.csv'), rows('lsat-nf2.csv')
raw_by_measurement = defaultdict(list)
raw_by_condition = defaultdict(list)
raw_blocks = defaultdict(list)
for i, r in enumerate(raw):
    raw_by_measurement[measurement(r)].append((i, r))
    raw_by_condition[condition(r)].append((i, r))
    raw_blocks[(r['source'], r['airfoil'], float(r['Re']))].append((i, r))
last = {k: rs[-1][1]['config'] for k, rs in raw_by_condition.items()}
conflicting = {k for k, rs in raw_by_measurement.items() if len({r['config'] for _, r in rs}) > 1}
used, block_used = Counter(), Counter()
joined, differences, ambiguous, order_mismatches = [], [], [], []
for i, r in enumerate(nf):
    k = measurement(r, True)
    raw_id, rr = raw_by_measurement[k][used[k]]
    used[k] += 1
    bk = (r['source'], r['airfoil'], float(r['Re']))
    block_raw_id, br = raw_blocks[bk][block_used[bk]]
    block_used[bk] += 1
    if block_raw_id != raw_id or measurement(br) != k:
        order_mismatches.append({'nf2_row_id': i, 'measurement_match_raw_id': raw_id, 'block_order_raw_id': block_raw_id})
    clean = r['config'] == 'clean' and rr['config'] == 'clean'
    dc = r['config'] == 'clean' and last[condition(r)] == 'clean'
    detail = {
        'nf2_row_id': i, 'nf2_csv_line': i + 2, 'raw_row_id': raw_id, 'raw_csv_line': raw_id + 2,
        'entry': r['source'] + '|' + r['airfoil'], 'Re': r['Re'], 'alpha': r['alpha'],
        'CL_meas': r['CL_meas'], 'CD_meas': r['CD_meas'], 'raw_config': rr['config'],
        'occurrence_clean': clean, 'last_write_clean': dc, 'conflicting_measurement_config': k in conflicting,
    }
    if clean != dc:
        differences.append(detail)
    if clean and k in conflicting:
        ambiguous.append(detail)
    joined.append((r, detail))
clean_rows = [(r, d) for r, d in joined if d['occurrence_clean']]
strict_rows = [(r, d) for r, d in clean_rows if not d['conflicting_measurement_config']]
write_csv('ambiguous_nf2_row_ids.csv', ambiguous)
write_csv('last_write_removed_clean_rows.csv', differences)

geo = json.loads((BASE / 'lsat-geometry.json').read_text())
entries = sorted({d['entry'] for _, d in clean_rows})
digests = {}
with zipfile.ZipFile(BASE / 'coord_seligFmt.zip') as coord, zipfile.ZipFile(BASE / 'Stec8.zip') as stec:
    for e in entries:
        path = geo[e]['path']
        archive, member = (coord, path[len('coords/'):]) if path.startswith('coords/') else (stec, path[len('stec8/'):])
        blob = archive.read(member)
        points = []
        for line in blob.decode('latin-1').splitlines()[1:]:
            p = line.split()
            if len(p) >= 2:
                try:
                    x, y = float(p[0]), float(p[1])
                except ValueError:
                    continue
                if -.5 <= x <= 1.5 and -.6 <= y <= .6:
                    points.append((x, y))
        xmin = min(x for x, y in points)
        chord = max(x for x, y in points) - xmin
        norm = [((x - xmin) / chord, y / chord) for x, y in points]
        # Exact ordered float64 normalized coordinates, no tolerant matching.
        packed = b''.join(struct.pack('<dd', x, y) for x, y in norm)
        digests[e] = {'path': path, 'byte_sha256': hashlib.sha256(blob).hexdigest(), 'normalized_coordinate_sha256': hashlib.sha256(packed).hexdigest()}
parent = {e: e for e in entries}
def find(e):
    while parent[e] != e:
        parent[e] = parent[parent[e]]
        e = parent[e]
    return e
def union(a, b):
    a, b = find(a), find(b)
    parent[max(a, b)] = min(a, b)
for field in ('nominal', 'byte_sha256', 'normalized_coordinate_sha256'):
    groups = defaultdict(list)
    for e in entries:
        groups[nominal(e) if field == 'nominal' else digests[e][field]].append(e)
    for members in groups.values():
        for e in members[1:]:
            union(members[0], e)
components = defaultdict(list)
for e in entries:
    components[find(e)].append(e)
group_id = {e: 'foilgroup_' + hashlib.sha256('\n'.join(components[find(e)]).encode()).hexdigest()[:12] for e in entries}
mapping = [{'entry':e, 'group_id':group_id[e], 'nominal_id':nominal(e), **digests[e], 'component_members':';'.join(components[find(e)])} for e in entries]
write_csv('entry_group_map.csv', mapping)

def overlap_summary(rows_, key):
    by_source = defaultdict(set)
    by_key = defaultdict(list)
    for r, d in rows_:
        e = d['entry']
        label = r['airfoil'] if key == 'raw_name' else nominal(e) if key == 'nominal' else digests[e][key] if key in digests[e] else group_id[e]
        by_source['stec8' if r['source'] == 'stec8' else 'vols'].add(label)
        by_key[label].append((r, d))
    common = by_source['stec8'] & by_source['vols']
    examples = []
    for label in sorted(common):
        subset = by_key[label]
        examples.append({'key':label, 'entries':sorted({d['entry'] for _,d in subset}),
                         'stec8_rows':sum(r['source']=='stec8' for r,d in subset),
                         'volume_rows':sum(r['source']!='stec8' for r,d in subset)})
    return {'overlap_groups':len(common), 'stec8_rows_with_train_overlap':sum(x['stec8_rows'] for x in examples),
            'volume_rows_with_train_overlap':sum(x['volume_rows'] for x in examples), 'groups':examples}

summary = {
    'id_convention':'nf2_row_id/raw_row_id are zero-based data-row indices; CSV line = index + 2',
    'raw_rows':len(raw), 'nf2_rows':len(nf), 'occurrence_clean_rows':len(clean_rows),
    'last_write_clean_rows':sum(d['last_write_clean'] for r,d in joined),
    'last_write_removed_clean_rows':len(differences),
    'conflicting_measurement_keys':len(conflicting), 'excluded_clean_ambiguous_rows':len(ambiguous),
    'conservative_clean_rows':len(strict_rows), 'measurement_vs_source_block_order_mismatches':order_mismatches,
    'entries':len(entries), 'nominal_geometry_union_groups':len(components),
    'grouping_policy':'Connected components joining explicit canonical nominal-family identities OR identical original geometry bytes OR identical ordered normalized float64 coordinates; conservative split independence, not physical equivalence.',
    'cross_source_overlap_conservative_rows':{k:overlap_summary(strict_rows,k) for k in ('raw_name','nominal','byte_sha256','normalized_coordinate_sha256','union')},
    'inputs_sha256':{n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in ('lsat-corpus.csv','lsat-nf2.csv','lsat-geometry.json','coord_seligFmt.zip','Stec8.zip')},
}
# Check the independently reconstructed arrays without fitting any estimator.
import numpy as np
occ_data = np.load(ROOT / 'model_development_20260906/reproduction/dataset_occurrence.npz')
dc_data = np.load(ROOT / 'model_development_20260906/reproduction/dataset.npz')
ambiguous_ids = {d['nf2_row_id'] for d in ambiguous}
in_domain_ids = set(map(int, occ_data['nf2_row_id']))
conservative_domain_ids = in_domain_ids - ambiguous_ids
strict_domain_rows = [(r, d) for r, d in strict_rows if d['nf2_row_id'] in conservative_domain_ids]
summary['in_domain'] = {
    'occurrence_rows':len(in_domain_ids), 'last_write_rows':len(dc_data['nf2_row_id']),
    'ambiguous_rows_excluded':len(in_domain_ids & ambiguous_ids),
    'conservative_rows':len(conservative_domain_ids),
    'last_write_removed_clean_rows':len(in_domain_ids - set(map(int,dc_data['nf2_row_id']))),
    'cross_source_overlap':{k:overlap_summary(strict_domain_rows,k) for k in ('raw_name','nominal','normalized_coordinate_sha256','union')},
}
xf = rows('lsat-xfoil.csv')
xfkeys = {(r['entry'],round(float(r['Re'])),round(float(r['alpha']),2)) for r in xf}
def common_counts(rowset):
    keys = [(d['entry'],round(float(r['Re'])),round(float(r['alpha']),2)) for r,d in rowset]
    return {'rows':len(keys),'unique_conditions':len(set(keys)),
            'common_rows':sum(k in xfkeys for k in keys),'common_unique_conditions':len(set(keys)&xfkeys)}
summary['cohort_common_counts'] = {
    'occurrence':common_counts(clean_rows),
    'last_write':common_counts([(r,d) for r,d in joined if d['last_write_clean']]),
    'conservative':common_counts(strict_rows),
}
fold_check=[]
for f in sorted(set(map(int, dc_data['fold']))):
    test=dc_data['fold']==f
    row={'fold':f,'test_rows':int(test.sum()),'train_rows':int((~test).sum())}
    for label, vals in (
        ('nominal',np.array([nominal(e) for e in dc_data['entry']])),
        ('exact_normalized_geometry',np.array([digests[e]['normalized_coordinate_sha256'] for e in dc_data['entry']])),
        ('union',np.array([group_id[e] for e in dc_data['entry']]))):
        overlap=set(vals[test])&set(vals[~test])
        row[label+'_overlap_groups']=len(overlap)
        row[label+'_affected_test_rows']=int(np.isin(vals[test],list(overlap)).sum())
    fold_check.append(row)
summary['recovered_raw_name_fold_overlap']=fold_check
(OUT / 'label_and_group_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('cross_source_overlap_conservative_rows','inputs_sha256')},indent=2))
print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='groups'} for k,v in summary['cross_source_overlap_conservative_rows'].items()},indent=2))
