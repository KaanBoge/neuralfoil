import io,json,tempfile,unittest,zipfile
from pathlib import Path
import run as w
class Tests(unittest.TestCase):
 def fixture(self):
  src={'code/integrity.py':b'# synthetic','code/test_integrity.py':b'# mock'};m={'files':{n:{'sha256':w.sha(b),'bytes':len(b)} for n,b in src.items()}};mb=json.dumps(m).encode();s=io.BytesIO()
  with zipfile.ZipFile(s,'w') as z:
   z.writestr('manifest.json',mb)
   for n,b in src.items():z.writestr(n,b)
   z.writestr('forbidden-scientific.bin',b'not-read')
  b=s.getvalue();a={'archive_sha256':w.sha(b),'inner_manifest_sha256':w.sha(mb),'source_members':{n:w.sha(v) for n,v in src.items()}};o={'files':{w.HREL:{'sha256':w.sha(b)}}};return b,a,o
 def test_two_source_ledger_only(self):
  b,a,o=self.fixture();l=[];s=w.selected_sources(b,a,o,l);self.assertEqual(set(s),{'integrity.py','test_integrity.py'});self.assertEqual(len(l),3);self.assertNotIn('forbidden-scientific.bin',str(l))
 def test_bad_archive(self):
  b,a,o=self.fixture();a['archive_sha256']='0'*64
  with self.assertRaises(ValueError):w.selected_sources(b,a,o,[])
 def test_bad_member(self):
  b,a,o=self.fixture();a['source_members']['code/integrity.py']='0'*64
  with self.assertRaises(ValueError):w.selected_sources(b,a,o,[])
 def test_no_overwrite_and_symlink(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t).resolve()/'x';w.write(p,{})
   with self.assertRaises(FileExistsError):w.write(p,{})
   q=p.with_name('link');q.symlink_to(p)
   with self.assertRaises(ValueError):w.raw(q)
 def test_approval_keys_scope(self):
  d={'phase':'eleven_synthetic_integrity_tests_only','source_sha256':'a','registry_sha256':'b','output':'/unused','runtime':'/opt/anaconda3/bin/python','seconds':120,'rss_bytes':536870912,'output_bytes':16777216,'workers':1};w.approve(d,'a','b','/unused')
  for k,v in [('extra',1),('workers',True),('seconds',121),('output','/other')]:
   with self.assertRaises(ValueError):w.approve({**d,k:v},'a','b','/unused')
 def test_start_missing_approval_no_attempt(self):
  with self.assertRaises(FileNotFoundError):w.execute('/private/tmp/no-such-phase2-approval-98246','0'*64)
if __name__=='__main__':unittest.main()
