"""Synthetic-only V2 resource, failure and predecessor tests."""
import json,os,select,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import adapter as a,certificates as c,study

class Successor(unittest.TestCase):
    def test_cumulative_before_child(self):
        with tempfile.TemporaryDirectory() as td,patch.object(a,'HERE',Path(td).resolve()),patch.object(a,'LOGICAL_CAP',100),patch.object(a,'CHILD_CAPS',{'certificates_produce':40}),patch.object(a,'RECEIPT_RESERVE',5):
            for phase in ['certificates_produce','certificates_replay']:
                p=a.HERE/phase;p.mkdir();(p/'old').write_bytes(b'x'*30)
            with self.assertRaises(OSError):a.reserve_child('certificates_produce',a.CONTEXTS[0])
            self.assertFalse((a.HERE/'certificates_produce'/a.CONTEXTS[0]).exists())
    def test_guard_prewrite_link_and_restore(self):
        original=Path.open;link=os.link
        with tempfile.TemporaryDirectory() as td,patch.object(a,'HERE',Path(td).resolve()),patch.object(a,'LOGICAL_CAP',100),patch.object(a,'RECEIPT_RESERVE',5):
            dest=a.HERE/'certificates_produce'/'context';dest.mkdir(parents=True)
            with a.storage_guard(dest,30):
                with (dest/'partial').open('xb') as f:f.write(b'x'*15)
                with self.assertRaises(OSError):os.link(dest/'partial',dest/'final')
                with self.assertRaises(ValueError):(a.HERE/'escape').open('xb')
            self.assertEqual((dest/'partial').stat().st_size,15);self.assertFalse((dest/'final').exists())
        self.assertIs(Path.open,original);self.assertIs(os.link,link)
    def test_timeout_retains_both_streams(self):
        # The timeout tests termination/stream retention, not interpreter startup.
        # A separate pipe acknowledges that BOTH stream writes were flushed.
        ready_read,ready_write=os.pipe();original=c.subprocess.Popen
        def started(command,**kwargs):
            p=original(command,pass_fds=(ready_write,),**kwargs)
            try:
                if not select.select([ready_read],[],[],5)[0]:raise AssertionError('child readiness failed; no retry')
                self.assertEqual(os.read(ready_read,1),b'R')
                return p
            except BaseException:
                p.kill();p.communicate();raise
        program=f'import os,sys,time;print("before",flush=True);print("errbefore",file=sys.stderr,flush=True);os.write({ready_write},b"R");time.sleep(5)'
        try:
            with patch.object(c.subprocess,'Popen',side_effect=started):
                code,out,err,error=c.run_child([sys.executable,'-B','-c',program],.1)
        finally:os.close(ready_read);os.close(ready_write)
        self.assertIsNotNone(error);self.assertIn('before',out);self.assertIn('errbefore',err);self.assertNotEqual(code,0)
    def test_aggregate_failed_and_not_run(self):
        with tempfile.TemporaryDirectory() as td,patch.object(a,'HERE',Path(td).resolve()):
            args=types.SimpleNamespace(phase='certificates_produce',registry_sha256='r',approval='unused',approval_sha256='ap')
            rows=[{'context':x,'sha256':'m'} for x in a.CONTEXTS]
            with patch.object(c,'phase_inputs',return_value=({}, {}, rows)),patch.object(a,'disk_preflight',return_value={}),patch.object(a,'inherited_final',return_value={}),patch.object(a,'reserve_child',return_value={}),patch.object(c,'run_child',return_value=(1,'preserved stdout','preserved stderr','timeout')):
                with self.assertRaises(RuntimeError):c.main_phase(args)
            out=a.HERE/args.phase;states=json.loads((out/'CONTEXT_STATUS.json').read_bytes())
            self.assertEqual(states[a.CONTEXTS[0]],'FAILED');self.assertTrue(all(states[x]=='NOT_RUN' for x in a.CONTEXTS[1:-1]))
            self.assertTrue((out/'FAILURE.json').exists());self.assertIn('preserved stdout',(out/f'process_{a.CONTEXTS[0]}.json').read_text())
    def test_recursive_producer_required_before_targets(self):
        replay={'status':'COMPLETE','phase':'certificates_replay','registry_sha256':'r','outputs':{},'summary':{'contexts':dict.fromkeys(a.CONTEXTS,{}),'predecessor_sha256':'producer-pin'}}
        seen=[]
        def read(path,pin,ledger):
            seen.append((str(path),pin))
            if pin=='producer-pin':raise ValueError('tampered producer')
            return replay
        with patch.object(a,'json_read',side_effect=read):
            with self.assertRaisesRegex(ValueError,'tampered producer'):study.complete('certificates_replay','rp','r',[])
        self.assertEqual(seen[-1][1],'producer-pin')
    def test_inherited_output_hash_is_required(self):
        p={'status':'COMPLETE','outputs':{'certificate.json':a.FINAL_CERT_SHA},'model_sha256':'m'}
        with patch.object(a,'json_read',return_value=p),patch.object(a,'authenticate_outputs',side_effect=ValueError('missing inherited output')):
            with self.assertRaisesRegex(ValueError,'missing inherited output'):a.inherited_final([],True)

if __name__=='__main__':unittest.main()
