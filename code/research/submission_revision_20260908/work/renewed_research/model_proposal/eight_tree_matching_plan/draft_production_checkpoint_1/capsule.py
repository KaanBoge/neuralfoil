"""Source-only finite old-proof extraction; no array/model reader."""
from fractions import Fraction as F

MODEL = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
CERT = 'ace9cb3a22e094ea509e53a0258f4ed573097454e2b7a7716b4f1c7335dfcd6f'
PC = 'dcb30c773b23f1a4dff91e5eb49058566793826aa9b699512b76390c5acc3704'
RC = 'af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa'
RR = 'ab0fc87f3a0f02eff3fff418309ecde9f416dde251e69ee41139c27a0d960f67'
PA = 'ce89fc902bd16dedbecbb70a5a7aa9b3fb6023dca0e1cd9b76ecfc89eefddcb7'
RA = '07f490cac240de2c4e4196c07d430e1bb05fab7379ff9a8fd6d990c9d4f0d2a8'
PR = '6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc'
CR = '2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26'
PARSER = 'ad4bbdf7b70fd862c959e3d916990890133f5ac4f9af714fb1e5ec6cc7706f1a'
FIXED = dict(old_certificate=CERT, old_producer_complete=PC, old_replay_complete=RC,
             old_replay_result=RR, old_producer_approval=PA, old_replay_approval=RA,
             old_producer_registry=PR, old_checker_registry=CR)


def decode(record):
    if type(record) != dict or set(record) != {'encoding', 'numerator', 'denominator'}:
        raise ValueError('rational fields')
    if record['encoding'] != 'signed_hex_fraction_v1':
        raise ValueError('rational codec')
    values = []
    for key in ('numerator', 'denominator'):
        s = record[key]
        if type(s) != str or len(s) > 1027:
            raise ValueError('rational text cap')
        n = int(s, 16)
        if hex(n) != s or abs(n).bit_length() > 4096:
            raise ValueError('canonical bounded integer')
        values.append(n)
    n, d = values
    if d <= 0:
        raise ValueError('positive denominator')
    f = F(n, d)
    if f.numerator != n or f.denominator != d:
        raise ValueError('reduced rational')
    return f


def interval(row):
    if type(row) != list or len(row) != 2:
        raise ValueError('interval shape')
    a, b = map(decode, row)
    if a > b:
        raise ValueError('empty interval')
    return a, b


def authenticate_ancestry(refs):
    pc, rc, rr, pa, ra = (refs[k] for k in ('old_producer_complete', 'old_replay_complete',
                                             'old_replay_result', 'old_producer_approval', 'old_replay_approval'))
    if pc['status'] != 'COMPLETE' or rc['status'] != 'COMPLETE':
        raise ValueError('old completion')
    if (pc['phase'] != 'four_tree_matching_produce' or rc['phase'] != 'four_tree_matching_replay'
            or pc['model_sha256'] != MODEL or rc['model_sha256'] != MODEL
            or pc['registry_sha256'] != PR or rc['producer_registry_sha256'] != PR
            or rc['checker_registry_sha256'] != CR or pc['approval_sha256'] != PA
            or rc['approval_sha256'] != RA or pc['outputs']['certificate.json'] != CERT
            or rc['outputs']['REPLAY.json'] != RR or rc['certificate_sha256'] != CERT
            or rc['producer_complete_sha256'] != PC):
        raise ValueError('old complete/output provenance')
    if (pa['real_execution_authorized'] is not True or ra['real_execution_authorized'] is not True
            or pa['registry_sha256'] != PR or ra['producer_registry_sha256'] != PR
            or ra['checker_registry_sha256'] != CR or ra['producer_complete_sha256'] != PC
            or ra['producer_approval_sha256'] != PA or ra['certificate_sha256'] != CERT
            or pa['model_sha256'] != MODEL or ra['model_sha256'] != MODEL):
        raise ValueError('old approval ancestry')
    if (rr['status'] != 'PASS_INDEPENDENT_FOUR_TREE_MATCHING_REPLAY'
            or rr['model_sha256'] != MODEL or rr['final'] != rc['summary']['final']):
        raise ValueError('old independent result')


def extract(cert, refs, source_sha, expected_pins):
    """Only after exact byte authentication and old bounded lexical parser."""
    if expected_pins != FIXED:
        raise ValueError('fixed predecessor identities')
    authenticate_ancestry(refs)
    if (cert['schema'] != 'FOUR_TREE_MATCHING_CERTIFICATE_V1' or cert['model_sha256'] != MODEL
            or cert['domain'] != 'FINITE_X62_V1' or len(cert['blocks']) != 100):
        raise ValueError('old certificate scope')
    if cert['final'] != refs['old_replay_result']['final']:
        raise ValueError('checked old final equality')
    initial = F(float.fromhex(cert['initial']))
    previous = (initial, initial)
    endpoints = []
    for j, block in enumerate(cert['blocks']):
        if block['block'] != j or block['stages'] != list(range(4*j, 4*j+4)):
            raise ValueError('all100 global stage identities')
        if interval(block['incoming']) != previous:
            raise ValueError('original chain continuity')
        previous = interval(block['outgoing'])
        endpoints.append(dict(stage=4*(j+1), outgoing=block['outgoing']))
    if previous != (decode(cert['final']['lower']), decode(cert['final']['upper'])):
        raise ValueError('final chain endpoint')
    return dict(schema='OLD_FOUR_GLOBAL_CHAIN_V1', model_sha256=MODEL, domain='FINITE_X62_V1',
                initial=cert['initial'], certificate_sha256=CERT, producer_complete_sha256=PC,
                replay_complete_sha256=RC, replay_result_sha256=RR,
                extraction_source_sha256=source_sha, endpoints=endpoints, final=cert['final'])


def validate(value, source_sha):
    keys = {'schema', 'model_sha256', 'domain', 'initial', 'certificate_sha256',
            'producer_complete_sha256', 'replay_complete_sha256', 'replay_result_sha256',
            'extraction_source_sha256', 'endpoints', 'final'}
    if type(value) != dict or set(value) != keys:
        raise ValueError('exact capsule fields')
    if (value['schema'] != 'OLD_FOUR_GLOBAL_CHAIN_V1' or value['model_sha256'] != MODEL
            or value['domain'] != 'FINITE_X62_V1' or value['certificate_sha256'] != CERT
            or value['producer_complete_sha256'] != PC or value['replay_complete_sha256'] != RC
            or value['replay_result_sha256'] != RR or value['extraction_source_sha256'] != source_sha):
        raise ValueError('capsule proof identity')
    if type(value['endpoints']) != list or len(value['endpoints']) != 100:
        raise ValueError('100global endpoints')
    endpoints = []
    for j, row in enumerate(value['endpoints']):
        if type(row) != dict or set(row) != {'stage', 'outgoing'} or type(row['stage']) != int or row['stage'] != 4*(j+1):
            raise ValueError('same GLOBAL stage')
        endpoints.append(interval(row['outgoing']))
    if endpoints[-1] != (decode(value['final']['lower']), decode(value['final']['upper'])):
        raise ValueError('capsule final equality')
    return endpoints
