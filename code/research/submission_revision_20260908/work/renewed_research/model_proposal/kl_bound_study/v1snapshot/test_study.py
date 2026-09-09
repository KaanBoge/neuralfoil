import io,json,tempfile,unittest
from pathlib import Path
from fractions import Fraction as F
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import inputs as ins
import run_experiment as r

class Study(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=r.codec_from_source()
    def fake(self,phase,arrays=None):
        x=object.__new__(ins.Inputs);x.phase=phase;x.events=[]
        b=io.BytesIO();np.savez(b,**(arrays or {'BASE_CD':np.array([1.]),'MEAS_CD':np.array([2.])}))
        x.buffers={'calibration/a.npz':b.getvalue(),'scoring/frame.npz':b.getvalue(),'scalars/a.json':b'{}','roles/a.json':b'{}'}
        return x
    def test_preflight_forbids_target(self):
        with self.assertRaises(ValueError):self.fake('preflight').array('calibration/a.npz',['MEAS_CD'])
    def test_preflight_forbids_scalars(self):
        with self.assertRaises(ValueError):self.fake('preflight').metadata('scalars/a.json')
    def test_score_forbids_frame(self):
        with self.assertRaises(ValueError):self.fake('score').scoring_arrays()
    def test_calibration_target_ledger(self):
        x=self.fake('calibrate');x.array('calibration/a.npz',['MEAS_CD'])
        self.assertEqual(x.events[0]['member'],'MEAS_CD')
    def test_only_materialized_members(self):
        x=self.fake('preflight');x.array('calibration/a.npz',['BASE_CD'])
        self.assertEqual(len(x.events),1)
    def test_member_missing(self):
        with self.assertRaises(KeyError):self.fake('calibrate').array('calibration/a.npz',['group'])
    def test_object_refused(self):
        x=self.fake('calibrate',{'MEAS_CD':np.array([object()],object)})
        with self.assertRaises(ValueError):x.array('calibration/a.npz',['MEAS_CD'])
    def roles(self):return {'proper_groups':['p'],'calibration_groups':['c'],'test_groups':['t'],'proper_indices':[0],'calibration_indices':[1],'test_indices':[2]}
    def test_roles_valid(self):r.verify_roles(self.roles())
    def test_role_overlap(self):
        x=self.roles();x['test_groups']=['c']
        with self.assertRaises(ValueError):r.verify_roles(x)
    def test_row_overlap(self):
        x=self.roles();x['test_indices']=[1]
        with self.assertRaises(ValueError):r.verify_roles(x)
    def native(self):return {'indices':np.array([0]),'BASE_CD':np.array([1.]),'core':np.array([1.]),'anchor':np.array([1.]),'gate':np.array([False])}
    def test_native_valid(self):r.schema(self.native())
    def test_native_bad_fallback(self):
        x=self.native();x['core'][0]=2
        with self.assertRaises(AssertionError):r.schema(x)
    def test_native_nonfinite(self):
        x=self.native();x['core'][0]=float('nan')
        with self.assertRaises(ValueError):r.schema(x)
    def test_matched_disagreement(self):
        a={'upper':F(1),'bound':F(1),'exact_mean':F(0),'t':.01,'rows':1,'groups':1,'group_means':{'a':F(0)}}
        old=json.loads(json.dumps(a,default=self.codec.encode));old['t']=.02
        with self.assertRaises(ValueError):r.matched(a,old,self.codec)
    def test_large_codec(self):
        x=F(2**20000+1,2**19999+1)
        self.assertEqual(self.codec.fraction(self.codec.encode(x)),x)
    def test_codec_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json';self.codec.write_json(p,{'x':F(1,3)});old=p.read_bytes()
            with self.assertRaises(FileExistsError):self.codec.write_json(p,{'x':F(1,2)})
            self.assertEqual(p.read_bytes(),old)
    def test_codec_no_partial(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json'
            with self.assertRaises(TypeError):self.codec.write_json(p,object())
            self.assertFalse(p.exists())
    def test_archive_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.zip';p.write_bytes(b'not the pinned archive')
            with self.assertRaises(ValueError):ins.Inputs(p,'preflight')
    def test_approval_wrong_phase(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);raw=json.dumps({'source_sha256':{},'external_source_sha256':{}}).encode();(root/'IMPLEMENTATION_FREEZE.json').write_bytes(raw)
            ap=root/'approval.json';a=json.dumps({'implementation_sha256':r.sha(raw),'authorized_phases':['preflight']}).encode();ap.write_bytes(a)
            args=SimpleNamespace(phase='calibrate',implementation_sha256=r.sha(raw),approval=ap,approval_sha256=r.sha(a))
            with patch.object(r,'HERE',root):
                with self.assertRaises(ValueError):r.authorize(args)
    def test_missing_predecessor(self):
        with tempfile.TemporaryDirectory() as td,patch.object(r,'HERE',Path('/private/tmp')/'does-not-exist-kl-synthetic'):
            with self.assertRaises(FileNotFoundError):r.predecessor('calibrate',{'predecessor_sha256':'bad'},'bad')
    def test_timeout_and_partial_preservation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve()
            argv=['run_experiment.py','preflight','--implementation-sha256','synthetic','--approval','synthetic','--approval-sha256','synthetic']
            def fail(*unused):
                (root/'preflight'/'partial.bin').write_bytes(b'preserved')
                raise TimeoutError('synthetic phase timeout')
            with patch.object(r,'HERE',root),patch.object(r.sys,'argv',argv),patch.object(r,'authorize',return_value=({},{})),patch.object(r,'predecessor'),patch.object(r,'codec_from_source',return_value=self.codec),patch.object(r,'Inputs',side_effect=fail):
                with self.assertRaises(TimeoutError):r.main()
                self.assertTrue((root/'preflight'/'FAILURE.json').exists())
                with self.assertRaises(FileExistsError):r.main()
                self.assertEqual((root/'preflight'/'partial.bin').read_bytes(),b'preserved')

if __name__=='__main__':unittest.main()
