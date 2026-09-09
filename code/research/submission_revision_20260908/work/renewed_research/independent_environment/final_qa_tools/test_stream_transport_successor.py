"""Independent negative regressions for the reviewed transport successor."""
import io,struct,tempfile,unittest,zipfile,sys
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[2]/'uncertainty_review/package_v6_plan'
sys.path.insert(0,str(SOURCE))
import stream_common as c
import write_evidence as w
import verify_evidence as v
import test_stream_evidence as fixtures

class Regressions(unittest.TestCase):
    def test_short_archive_and_payload_writes_rejected(self):
        class Short(io.BytesIO):
            def write(self,b):return super().write(b[:1])
        with self.assertRaises(OSError):w.CappedFile(Short(),c.Clock()).write(b'abc')
        with self.assertRaises(OSError):v.write_chunk(Short(),b'abc')
    def test_actual_central_count_checked_before_zipfile(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'small.zip'
            with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for n in ['a','b','c']:z.writestr(n,b'x')
            raw=p.read_bytes();tail=list(struct.unpack('<4s4H2LH',raw[-22:]));tail[3]=tail[4]=1
            p.write_bytes(raw[:-22]+struct.pack('<4s4H2LH',*tail))
            with patch.object(c,'MAX_FILES',1),patch.object(zipfile,'ZipFile',side_effect=AssertionError('premature ZipFile')):
                with self.assertRaises(ValueError):v.directory_admission(p)
    def test_actual_disk_bytes_rechecked(self):
        fixture=fixtures.Tests();fixture.setUp()
        try:
            fixture.create();name,h=fixture.auth('VERIFY_EXTRACT','extract');original=v.verify_disk
            def corrupt(out,expected,clock):
                target=out/'payload/evidence/proof.txt';target.write_bytes(b'X'*target.stat().st_size)
                return original(out,expected,clock)
            with patch.object(v,'verify_disk',corrupt):
                with self.assertRaises(ValueError):v.run(fixture.root,name,h,'extract')
            self.assertTrue((fixture.root/'extract/FAILURE.json').exists())
            self.assertFalse((fixture.root/'extract/COMPLETE.json').exists())
        finally:fixture.tearDown()
    def test_source_role_conflict_before_output(self):
        fixture=fixtures.Tests();fixture.setUp()
        try:
            source=fixture.root/'write_evidence.py';new=b'X'*source.stat().st_size
            fixture.sel['files']=[dict(source='write_evidence.py',target='old/source.py',sha256=c.digest(new),bytes=len(new))]
            fixture.put('selection.json',fixture.sel);name,h=fixture.auth()
            with self.assertRaises(ValueError):w.run(fixture.root,name,h,'create')
            self.assertFalse((fixture.root/'create').exists())
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
