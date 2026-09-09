"""Root adopts the reviewed synthetic gate and authorizes one sole-model phase.

No model/feature/target arrays are opened; only pinned source and metadata bytes.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT/'model_proposal/four_tree_matching_plan'
REG_SHA = '6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc'
CHECK_SHA = '2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26'
GATE_SHA = 'b5fc0fa6463f2704519df2a4be658cf21d4afbbcb7a52bf5d4e6c5035b86f6a0'


def checked(path, pin):
    path = Path(path).absolute()
    if not path.is_relative_to(ROOT) or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('scoped metadata/source')
    if path.suffix not in ('.json', '.py', '.md') or path.stat().st_size > 2**20:
        raise ValueError('no scientific payload admission')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('pinned source/metadata changed '+str(path))
    return raw


def main():
    outputs = [PLAN/n for n in ('ROOT_SOURCE_REVIEW.json', 'COLD_GATE_PASS.json', 'ROOT_PRODUCER_APPROVAL.json')]
    if any(p.exists() for p in outputs) or (PLAN/'attempt_1').exists():
        raise FileExistsError('preserve prior authorizations/attempts')
    reg = json.loads(checked(PLAN/'REGISTRY_SOURCE_V1.json', REG_SHA))
    creg = json.loads(checked(HERE/'CHECKER_SOURCE_REGISTRY_V1.json', CHECK_SHA))
    if creg['producer_registry_sha256'] != REG_SHA or creg['sources'] != reg['checker_sources']:
        raise ValueError('dual source registries')
    for name, pin in reg['sources'].items():
        checked(PLAN/name, pin)
    for family in ('checker_sources', 'predecessors'):
        for entry in reg[family].values():
            checked(ROOT/entry['path'], entry['sha256'])
    checked(HERE/'ROOT_SOURCE_REVIEW.md', '474376621e01f530793baab0541f41a088dc5f4c006033ffc0760ec50a1a1058')
    checked(HERE/'DUAL_REGISTRY_QA.json', 'ccfe20a950b7865de2100ca9466b97aebce0ddb3ab0ae335fc88764feef1adb0')
    qa = json.loads(checked(HERE/'COLD_RECEIPT_QA.json',
                            '1881b3038f1bcc4aa01a97fa5655d268c6545df1bd247e1722a22806e541c8b5'))
    if qa['status'] != 'PASS_SAVED_SYNTHETIC_RECEIPT_AUDIT':
        raise ValueError('reviewed cold receipt')
    gate_raw = checked(PLAN/'cold_attempt_1/COMPLETE.json', GATE_SHA)
    gate = json.loads(gate_raw)
    if (gate['status'] != 'PASS_FIXED_135000_GATE' or gate['registry_sha256'] != REG_SHA
            or gate['checker_registry_sha256'] != CHECK_SHA or gate['pair_classifications'] != 135000
            or gate['actual_model_access'] is not False
            or any((PLAN/'cold_attempt_1'/sub/'FAILURE.json').exists() for sub in ('', 'producer', 'checker'))):
        raise ValueError('one complete synthetic-only gate')
    for phase, cap in (('producer', 128*2**20), ('checker', 256*2**20)):
        item = gate[phase]
        if not 0 < item['seconds'] < 120 or not 0 < item['owned_estimate'] <= cap:
            raise ValueError('unchanged cold resource limits')
        receipt = json.loads(checked(PLAN/'cold_attempt_1'/phase/'COMPLETE.json', item['complete_sha256']))
        if receipt['summary']['counts'] != {'stages': 400, 'blocks': 100, 'paths': 6000,
                                           'path_edges': 47600, 'pair_classifications': 135000,
                                           'feasible_pairs': 135000}:
            raise ValueError('complete fixed cold fixture')
    checked(HERE/'launch.py', '2e51ced9a59a46ded516362c0edd5a9ee03328c64679e486159af6a511766bd2')
    checked(HERE/'test_launch.py', 'c500bfbb2afb424ef68630671e1a72706f1de4127ac179dc198fcf848223b60a')
    review = {'status': 'PASS_SOURCE_REVIEW', 'registry_sha256': REG_SHA,
              'checker_registry_sha256': CHECK_SHA,
              'root_narrative_sha256': '474376621e01f530793baab0541f41a088dc5f4c006033ffc0760ec50a1a1058',
              'dual_registry_qa_sha256': 'ccfe20a950b7865de2100ca9466b97aebce0ddb3ab0ae335fc88764feef1adb0',
              'cold_receipt_qa_sha256': '1881b3038f1bcc4aa01a97fa5655d268c6545df1bd247e1722a22806e541c8b5',
              'root_test_invocations': {'producer_infrastructure': 39, 'checker_entry': 21, 'capture': 4},
              'external_capture_source_sha256': '2e51ced9a59a46ded516362c0edd5a9ee03328c64679e486159af6a511766bd2',
              'external_capture_bytes': 65536, 'external_complete_phase_seconds': 900,
              'external_capture_local_log_files': False,
              'no_accuracy_or_optimality_claim': True}
    review_raw = (json.dumps(review, sort_keys=True, indent=2)+'\n').encode()
    review_sha = hashlib.sha256(review_raw).hexdigest()
    ap = {'phase': 'four_tree_matching_produce', 'registry_sha256': REG_SHA,
          'checker_registry_sha256': CHECK_SHA, 'model_sha256': reg['model_sha256'],
          'domain': 'FINITE_X62_V1', 'seconds': 900, 'workers': 1,
          'owned_cap': 128*2**20, 'output_cap': 64*2**20,
          'real_execution_authorized': True, 'output': 'attempt_1',
          'source_review_sha256': review_sha, 'synthetic_gate_sha256': GATE_SHA}
    ap_raw = (json.dumps(ap, sort_keys=True, indent=2)+'\n').encode()
    for path, raw in zip(outputs, (review_raw, gate_raw, ap_raw)):
        with path.open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'approval_sha256': hashlib.sha256(ap_raw).hexdigest(),
                      'source_review_sha256': review_sha, 'gate_sha256': GATE_SHA,
                      'actual_execution_performed': False}))


if __name__ == '__main__':
    main()
