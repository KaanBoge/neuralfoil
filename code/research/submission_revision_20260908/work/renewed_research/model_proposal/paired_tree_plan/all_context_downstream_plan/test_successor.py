import ast
import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import run


def modules():
    specs = [('legacy_adapter', run.LEGACY / 'adapter.py'), ('storage', run.HERE / 'storage.py'),
             ('adapter', run.HERE / 'adapter.py'), ('study_inputs', run.LEGACY / 'study_inputs.py'),
             ('downstream_study', run.HERE / 'study.py')]
    return run.loaded({n: (p, p.read_bytes()) for n, p in specs})


class Tests(unittest.TestCase):
    def test_original_pins(self):
        run.raw(run.LEGACY / 'adapter.py', run.OLD_ADAPTER)
        run.raw(run.LEGACY / 'study_inputs.py', run.OLD_INPUTS)
        run.raw(run.LEGACY / 'REGISTRY_v3.json', run.OLD_REGISTRY)

    def test_math_ast_only_writer_substitutions(self):
        original = (run.LEGACY / 'study.py').read_text()
        original = original.replace("codec.write_json(out/name,result);outputs[name]=a.sha((out/name).read_bytes())", "outputs[name]=a.scalar(out/name,result,codec)")
        original = original.replace("with (out/name).open('xb') as f:np.savez_compressed(f,**z,**{k:v for k,v in table.items() if k not in z})\n        outputs[name]=a.sha((out/name).read_bytes())", "outputs[name]=a.npz(out/name,{**z,**{k:v for k,v in table.items() if k not in z}})")
        original = original.replace("pd.DataFrame(table).to_csv(out/name,index=False,mode='x');outputs[name]=a.sha((out/name).read_bytes())", "outputs[name]=a.csv(out/name,pd.DataFrame(table))")
        original = original.replace("t.to_csv(path,index=False,mode='x');outputs[path.name]=a.sha(path.read_bytes())", "outputs[path.name]=a.csv(path,t)")
        def functions(src):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(src).body
                    if isinstance(n, ast.FunctionDef) and n.name != 'complete'}
        self.assertEqual(functions(original), functions((run.HERE / 'study.py').read_text()))

    def test_imports_no_members_and_restoration(self):
        import sys
        sentinel = sys.modules.get('adapter')
        with modules() as ms:
            self.assertIsNone(ms['adapter']._bound)
            self.assertIsNone(ms['adapter']._budget)
            self.assertEqual(len(ms['adapter'].names('calibrate')), 53)
            self.assertEqual(len(ms['adapter'].names('score')), 40)
            self.assertEqual(len(ms['adapter'].roots()), 11)
        self.assertIs(sys.modules.get('adapter'), sentinel)

    def test_inherited_engines_mocked_code_and_restoration(self):
        import sys
        with modules() as ms, tempfile.TemporaryDirectory() as temp:
            a, inputs = ms['adapter'], ms['study_inputs']
            a.ROOT = Path(temp).resolve()
            folder = a.ROOT / 'model_proposal/kl_bound_study/portable_plan'
            folder.mkdir(parents=True)
            sources = {'integrity': 'VALUE = 1\n',
                       'shared': "import sys, types\ndef engines(parent,addon):\n m=types.ModuleType('parent_policy')\n exec(parent.code('code/policy.py'),m.__dict__)\n sys.modules['parent_policy']=m\n return [m.VALUE]*7\n"}
            reg = {'external_sources': {}}
            for name, src in sources.items():
                (folder / (name + '.py')).write_text(src)
                reg['external_sources']['model_proposal/kl_bound_study/portable_plan/' + name + '.py'] = hashlib.sha256(src.encode()).hexdigest()
            class MockArchive:
                def __init__(self): self.access = []
                def code(self, name):
                    if name != 'code/policy.py': raise ValueError('mock source name')
                    self.access.append(name)
                    return b'VALUE = 123\n'
            parent = MockArchive(); sentinel = sys.modules.get('parent_policy'); ledger = []
            with inputs.engines(reg, parent, MockArchive(), ledger) as eng:
                self.assertEqual(eng[:7], (123,) * 7)
                self.assertEqual(len(eng), 8)
            self.assertEqual(parent.access, ['code/policy.py'])
            self.assertEqual(len(ledger), 2)
            self.assertIs(sys.modules.get('parent_policy'), sentinel)

    def test_source_barrier_precedes_execution(self):
        args = types.SimpleNamespace(registry_sha256='r', entry_sha256='e')
        with patch.object(run, 'raw', side_effect=ValueError('bad pin')), patch.object(run, 'loaded') as execute:
            with self.assertRaises(ValueError): run.execute(args)
            execute.assert_not_called()

    def test_complete_adapter_surface(self):
        with modules() as ms:
            for path in (run.HERE / 'study.py', run.LEGACY / 'study_inputs.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'a':
                        self.assertTrue(hasattr(ms['adapter'], node.attr), node.attr)

    def test_dual_registry_and_approval_chain(self):
        with modules() as ms:
            a = ms['adapter']; old = ms['legacy_adapter']
            inherited = dict(registry_sha256=a.LEGACY_SHA, producer_sha256=a.PRODUCER_SHA,
                             replay_sha256='r' * 64, producer_approval_sha256='p' * 64,
                             replay_approval_sha256='q' * 64, producer_approval_path='producer.json',
                             replay_approval_path='replay.json')
            a._bound = ({'inherited': inherited}, 'downstream', {})
            contexts = {c: {'complete_sha256': c} for c in a.CONTEXTS[:-1]}
            def js(path, pin, ledger):
                if path.name == 'REGISTRY_v3.json': return {'sources': {}, 'external_sources': {}}
                phase = 'producer' if 'certificates_produce' in str(path) else 'replay'
                return {'approval_sha256': inherited[phase + '_approval_sha256'],
                        'summary': {'contexts': contexts, 'predecessor_sha256': a.PRODUCER_SHA}}
            with patch.object(a, 'json_read', side_effect=js), patch.object(old, 'authenticate', return_value={'predecessor_sha256': a.PRODUCER_SHA}), patch.object(old, 'certificate_chain', return_value='passed') as chain:
                self.assertEqual(a.certificate_chain('certificates_replay', 'r' * 64, 'downstream', []), 'passed')
                self.assertEqual(chain.call_args.args[2], a.LEGACY_SHA)
                with self.assertRaises(ValueError): a.certificate_chain('certificates_replay', 'r' * 64, a.LEGACY_SHA, [])
                with self.assertRaises(ValueError): a.certificate_chain('certificates_replay', 'wrong', 'downstream', [])
            with patch.object(a, 'json_read', side_effect=js), patch.object(old, 'authenticate', return_value={'predecessor_sha256': 'wrong'}):
                with self.assertRaises(ValueError): a.certificate_chain('certificates_replay', 'r' * 64, 'downstream', [])

    def test_new_receipt_rejects_wrong_registry_failure_or_path(self):
        with modules() as ms:
            a, study = ms['adapter'], ms['downstream_study']
            good = dict(status='COMPLETE', registry_sha256='new', phase='preflight',
                        inherited_certificate_registry_sha256=a.LEGACY_SHA,
                        outputs={}, summary={'predecessor_sha256': 'oldreceipt'})
            with patch.object(a, 'json_read', return_value=good), patch.object(a, 'certificate_chain', return_value={}):
                self.assertEqual(study.complete('preflight', 'pin', 'new', []), good)
                with self.assertRaises(ValueError): study.complete('preflight', 'pin', 'old', [])
                good['outputs'] = {'../escape': 'h'}
                with self.assertRaises(ValueError): study.complete('preflight', 'pin', 'new', [])

    def test_attempt_failure_metadata_and_no_success(self):
        with modules() as ms, tempfile.TemporaryDirectory() as temp:
            a = ms['adapter']; root = Path(temp).resolve()
            a.HERE = root; a._bound = ({}, 'test', {})
            with patch.object(a, 'roots', return_value=[root / p for p in a.PHASES]):
                def fail(out, ledger, outputs, deadline):
                    ledger.extend([None] * 10000)
                    raise RuntimeError('synthetic failure')
                with self.assertRaises(RuntimeError): a.attempt(root / 'score', {'phase': 'score'}, fail)
                self.assertFalse((root / 'score/COMPLETE.json').exists())
                raw = (root / 'score/FAILURE.json').read_bytes()
                self.assertLess(len(raw), 1024)
                self.assertFalse(json.loads(raw)['access_ledger_complete'])

    def test_attempt_complete_size_counted(self):
        with modules() as ms, tempfile.TemporaryDirectory() as temp:
            a = ms['adapter']; root = Path(temp).resolve()
            a.HERE = root; a._bound = ({}, 'test', {})
            with patch.object(a, 'roots', return_value=[root / p for p in a.PHASES]):
                result = a.attempt(root / 'preflight', {'phase': 'preflight'}, lambda *args: {})
                size = sum(p.stat().st_size for p in (root / 'preflight').iterdir())
                self.assertGreater(size, result['cumulative_bytes_before_complete'])
                self.assertEqual(result['status'], 'COMPLETE')
                self.assertEqual((root / 'preflight/COMPLETE.json').read_bytes(),
                                 (root / 'preflight/COMPLETE.pending.json').read_bytes())
                with self.assertRaises(FileExistsError): a.attempt(root / 'preflight', {'phase': 'preflight'}, lambda *args: {})

    def test_commit_failure_retains_pending_without_complete(self):
        with modules() as ms, tempfile.TemporaryDirectory() as temp:
            a = ms['adapter']; root = Path(temp).resolve()
            a.HERE = root; a._bound = ({}, 'test', {})
            with patch.object(a, 'roots', return_value=[root / p for p in a.PHASES]), patch.object(a.os, 'link', side_effect=OSError('synthetic link failure')):
                with self.assertRaises(OSError): a.attempt(root / 'preflight', {'phase': 'preflight'}, lambda *args: {})
                self.assertTrue((root / 'preflight/COMPLETE.pending.json').exists())
                self.assertTrue((root / 'preflight/FAILURE.json').exists())
                self.assertFalse((root / 'preflight/COMPLETE.json').exists())


if __name__ == '__main__': unittest.main()
