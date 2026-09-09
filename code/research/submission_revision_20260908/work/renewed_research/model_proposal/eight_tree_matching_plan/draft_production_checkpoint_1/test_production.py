"""Small source/metadata mocks only; never materializes actual inputs."""
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
import zipfile
import adapter
import capsule as c
import production_support as s
import prototype as p
import run_phase as r


def mock_capsule():
    return dict(schema='OLD_FOUR_GLOBAL_CHAIN_V1', model_sha256=c.MODEL, domain='FINITE_X62_V1',
                initial=0.0.hex(), certificate_sha256=c.CERT, producer_complete_sha256=c.PC,
                replay_complete_sha256=c.RC, replay_result_sha256=c.RR,
                extraction_source_sha256='a'*64,
                endpoints=[dict(stage=4*(j+1), outgoing=p.ep((F(-1),F(1)))) for j in range(100)],
                final=dict(lower=p.encode(-1), upper=p.encode(1), B=p.encode(p.structural((F(-1),F(1))))))


class ProductionTests(unittest.TestCase):
    def test_capsule_exact100_and_identity(self):
        q = mock_capsule()
        self.assertEqual(len(c.validate(q,'a'*64)),100)
        for field in ('model_sha256','certificate_sha256','replay_complete_sha256','extraction_source_sha256'):
            bad=copy.deepcopy(q);bad[field]='b'*64
            with self.assertRaises(ValueError): c.validate(bad,'a'*64)
        for change in ('duplicate','missing','reorder','endpoint'):
            bad=copy.deepcopy(q)
            if change=='duplicate': bad['endpoints'][1]=bad['endpoints'][0]
            if change=='missing': bad['endpoints'].pop()
            if change=='reorder': bad['endpoints'].reverse()
            if change=='endpoint': bad['endpoints'][-1]['outgoing']=p.ep((F(0),F(0)))
            with self.assertRaises(ValueError):c.validate(bad,'a'*64)

    def test_rational_noncanonical(self):
        for n,d in [('0x00','0x1'),('-0x0','0x1'),('0x2','0x2'),('0x1','-0x1')]:
            with self.assertRaises(ValueError):c.decode(dict(encoding='signed_hex_fraction_v1',numerator=n,denominator=d))

    def test_approval_exact(self):
        a=dict(phase='capsule',registry_sha256='a'*64,entrypoint_sha256='b'*64,
               output='capsule_attempt_1',seconds=900,workers=1,owned_cap=256*2**20,
               output_cap=64*2**20,model_sha256=c.MODEL,domain='FINITE_X62_V1',
               python='3.13.9',actual_execution_authorized=True,source_review_sha256='c'*64)
        r.approval(a,'capsule','a'*64,'b'*64)
        for key,value in [('extra',1),('output','another'),('workers',True),('seconds',901),('actual_execution_authorized',False)]:
            b=dict(a);b[key]=value
            with self.assertRaises(ValueError):r.approval(b,'capsule','a'*64,'b'*64)

    def test_auth_buffer_and_json_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td).resolve()/'a.json';path.write_bytes(b'{"x":1}')
            ledger=[];raw=s.read(path,s.sha(path.read_bytes()),ledger,100)
            self.assertEqual(s.parse(raw,ledger,'synthetic'),{'x':1})
            self.assertEqual([e['operation'] for e in ledger],['authenticated_bytes','JSON_parse'])
            with self.assertRaises(ValueError):s.read(path,'0'*64,[],100)
            with self.assertRaises(ValueError):s.parse(b'{"x":1,"x":2}',[],'duplicate')

    def test_encoder_bounds_before_string_allocation(self):
        with self.assertRaises(ValueError):s.line_bytes({'value':'x'*16385})
        with self.assertRaises(ValueError):s.line_bytes({'value':2**65})

    def test_store_timeout_and_partial_retained(self):
        with tempfile.TemporaryDirectory() as td:
            store=s.Store(Path(td).resolve()/'attempt',time.monotonic()+10)
            store.begin();store.record({'kind':'synthetic'})
            store.deadline=time.monotonic()-1
            with self.assertRaises(TimeoutError):store.record({'next':True})
            store.close_partial()
            store.json('FAILURE.json',{'status':'synthetic timeout'},emergency=True)
            self.assertEqual((store.path/'certificate.jsonl').read_bytes(),b'{"kind":"synthetic"}\n')
            with self.assertRaises(FileExistsError):s.Store(store.path,time.monotonic()+10)

    def test_symlink_ancestor_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();(root/'real').mkdir();(root/'link').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaises(ValueError):s.Store(root/'link'/'attempt',time.monotonic()+1)

    def test_npz_names_before_array_loading(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('../bad.npy',b'not an array')
        with self.assertRaises(ValueError):adapter.model_shape(raw.getvalue(),('initial',))


if __name__=='__main__':unittest.main()
