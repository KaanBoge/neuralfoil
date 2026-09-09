import unittest,tempfile,json,io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
import shared,integrity,replay
class Successor(unittest.TestCase):
    def test_float_near_count_rejected(self):
        for col in ['rows','groups','draws','nf2_row_id','interventions','negative_groups']:
            with patch.dict(shared.COUNTS,{'synthetic':1}):
                sink=[]
                with self.assertRaises(ValueError):shared.compare_tables('synthetic',pd.DataFrame({col:[1.+1e-12]}),(col+'\n1\n').encode(),difference_sink=sink)
                self.assertEqual(len(sink),1)
    def test_float_exact_count_accepted(self):
        with patch.dict(shared.COUNTS,{'synthetic':1}):self.assertEqual(shared.compare_tables('synthetic',pd.DataFrame({'rows':[1.]}),b'rows\n1\n'),[])
    def test_expected_bool_rejects_near_float(self):
        with patch.dict(shared.COUNTS,{'synthetic':1}):
            with self.assertRaises(AssertionError):shared.compare_tables('synthetic',pd.DataFrame({'advance':[1.-1e-12]}),b'advance\nTrue\n')
    def test_local_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);buf={}
            for n in ['replay.py','shared.py','integrity.py']:(root/n).write_bytes(b'synthetic');buf['code/'+n]=b'synthetic'
            with patch.object(replay,'__file__',str(root/'replay.py')):
                self.assertEqual(len(replay.bind_local(buf)),3)
                (root/'shared.py').write_bytes(b'changed')
                with self.assertRaises(ValueError):replay.bind_local(buf)
    def test_missing_parent(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):integrity.verified_members(Path(td).resolve()/'missing.zip','a','b')
    def test_archive_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();(root/'real').mkdir();(root/'alias').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaises(ValueError):integrity.verified_members(root/'alias'/'missing.zip','a','b')
    def test_reader_ledger_and_tamper(self):
        b={'a.json':b'{"x":1}','a.csv':b'x\n1\n'};log=[];r=shared.Reader(b,log,'synthetic')
        r.json('a.json');r.csv('a.csv');self.assertEqual([v['operation'] for v in log],['JSON parse','pandas.read_csv'])
        b['a.json']=b'{}'
        with self.assertRaises(ValueError):r.json('a.json')
    def test_native_scalar_refusals(self):
        with self.assertRaises(AssertionError):shared.native_equal({'p':np.array([1.])},{'p':np.array([1.0001])})
        with self.assertRaises(ValueError):shared.scalar_equal({'t':.1},{'t':.2},SimpleNamespace(encode=lambda x:x))
    def test_roles_maps_wrong(self):
        z={'indices':np.array([1]),'nf2_row_id':np.array([10])};role={'proper_groups':['p'],'calibration_groups':['c'],'test_groups':['t'],'calibration_indices':[2],'calibration_nf2_row_ids':[10]}
        with self.assertRaises(AssertionError):shared.validate_roles(z,role)
        role['calibration_indices']=[1];role['test_groups']=['c']
        with self.assertRaises(ValueError):shared.validate_roles(z,role)
    def test_overlay_source_fixture(self):
        source=Path(__file__).resolve().parents[1]/'run_experiment.py'
        pinraw=(source.parent/'IMPLEMENTATION_FREEZE_v2.json').read_bytes()
        self.assertEqual(integrity.sha(pinraw),'fc44b641a13958487fa69e8655c29c30b43fbbcbc9c7fe986ace40de5e07ec08')
        raw=source.read_bytes();self.assertEqual(integrity.sha(raw),json.loads(pinraw)['source_sha256']['run_experiment.py']);code,_=shared.extract(raw,['overlay'])
        m=shared.module('synthetic_overlay','import numpy as np\nimport pandas as pd\n'+code,{'NEW_LABELS':shared.LABELS,'EXTERNAL':shared.EXT})
        f=pd.DataFrame({'split':['h','h'],'nf2_row_id':[1,2],'mean8_CD':[.1,.2],'bool':[True,False],'obj':pd.Series([None,'s'],dtype=object)})
        p=pd.DataFrame({'nf2_row_id':[2,1],'BASE_CD':[.2,.1]})
        for label in shared.LABELS:
            for k in [label,label+'__strength',label+'__effective_fraction',label+'__intervened']:p[k]=[.2,.1]
        old=f.copy(deep=True);out=m.overlay(f,{'h':p});pd.testing.assert_frame_equal(out[old.columns],old,check_exact=True)
        p['nf2_row_id']=[1,1]
        with self.assertRaises(ValueError):m.overlay(old.copy(),{'h':p})
        p['nf2_row_id']=[1,99]
        with self.assertRaises(ValueError):m.overlay(old.copy(),{'h':p})
        with self.assertRaises(ValueError):m.overlay(old.copy(),{'h':p.iloc[:1]})
        ext=old.copy();ext['split']='SG_exposed';p['indices']=[1,0]
        with self.assertRaises(AssertionError):m.overlay(ext,{'SG_exposed':p})
    def test_authentication_failure_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td).resolve()/'out';args=SimpleNamespace(output=out,approval_sha256='synthetic',archive_sha256='synthetic',manifest_sha256='synthetic')
            with patch.object(replay,'authenticate',side_effect=ValueError('synthetic source failure')):
                with self.assertRaises(ValueError):replay.main(args)
            self.assertTrue((out/'ATTEMPT.json').exists());self.assertTrue((out/'FAILURE.json').exists());self.assertFalse((out/'COMPLETE.json').exists())
if __name__=='__main__':unittest.main()
