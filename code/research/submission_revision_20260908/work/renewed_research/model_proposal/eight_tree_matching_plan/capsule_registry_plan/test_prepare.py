import json
from pathlib import Path
import tempfile
import unittest
import prepare as p


class Tests(unittest.TestCase):
    def reader(self, events, broken=False):
        def read(kind,path,h):
            events.append((kind,path,h))
            self.assertNotIn('certificate.json',path)
            self.assertFalse(path.endswith('.npz'))
            if kind != 'metadata':
                return b'synthetic source'
            if path == p.INPUTS['old_producer_complete'][0]:
                d=dict(status='FAIL' if broken else 'COMPLETE',outputs={'certificate.json':p.INPUTS['old_certificate'][1]})
            elif path == p.INPUTS['old_replay_complete'][0]:
                d=dict(status='COMPLETE',certificate_sha256=p.INPUTS['old_certificate'][1],
                       producer_complete_sha256=p.INPUTS['old_producer_complete'][1],
                       outputs={'REPLAY.json':p.INPUTS['old_replay_result'][1]})
            else:
                d={}
            return json.dumps(d).encode()
        return read

    def test_finite_scope_and_deferred_certificate(self):
        events=[]
        r=p.build(self.reader(events))
        self.assertEqual(len(events),13)
        self.assertEqual(len(r['inputs']),8)
        self.assertEqual(set(r),{'schema','phase','sources','helpers','inputs'})
        self.assertEqual(r['phase'],'capsule')

    def test_failed_predecessor(self):
        with self.assertRaises(ValueError):
            p.build(self.reader([],True))

    def test_aggregate_metadata_admission(self):
        with self.assertRaises(MemoryError):
            p.build(lambda kind,*_: b' '*(22000) if kind=='metadata' else b's')

    def test_approval_exact(self):
        a=dict(phase='capsule_registry_metadata_preparation',entrypoint_sha256='a'*64,
               output='CAPSULE_REGISTRY.json',attempt='capsule_registry_preparation_attempt_1',
               seconds=120,workers=1,output_cap=2**20,metadata_only=True,
               actual_capsule_execution_authorized=False,preparation_authorized=True)
        p.check_approval(a,'a'*64)
        for k,v in [('output','other'),('extra',0),('actual_capsule_execution_authorized',True)]:
            with self.assertRaises(ValueError):
                p.check_approval(dict(a,**{k:v}),'a'*64)

    def test_serialization_and_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t).resolve()/'out.json'
            with self.assertRaises(TypeError):
                p.write(path,object())
            self.assertFalse(path.exists())
            p.write(path,{'ok':True})
            first=path.read_bytes()
            with self.assertRaises(FileExistsError):
                p.write(path,{'changed':True})
            self.assertEqual(path.read_bytes(),first)

    def test_symlink_and_hash_refusal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            file=root/'f';file.write_bytes(b'abc')
            link=root/'link';link.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError):p.safe(link/'f')
            with self.assertRaises(ValueError):p.read(file,'0'*64,[])


if __name__=='__main__':unittest.main()
