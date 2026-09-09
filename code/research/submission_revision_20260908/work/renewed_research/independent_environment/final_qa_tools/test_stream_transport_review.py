"""Independent small counterexamples; no actual selected scientific payloads."""
import io,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import sys
SOURCE=Path(__file__).resolve().parents[2]/'uncertainty_review/package_v6_plan'
sys.path.insert(0,str(SOURCE))
import stream_common as c
import write_evidence as w
import verify_evidence as v
import test_stream_evidence as fixtures

class Counterexamples(unittest.TestCase):
    def test_short_write_accepted(self):
        class Short(io.BytesIO):
            def write(self,b):return super().write(b[:1])
        raw=Short();out=w.CappedFile(raw,c.Clock())
        self.assertEqual(out.write(b'abc'),1)
        self.assertEqual(raw.getvalue(),b'a')

    def test_lying_central_count_passes_preallocation(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'small.zip'
            with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for n in ['a','b','c']:z.writestr(n,b'x')
            raw=p.read_bytes();tail=list(struct.unpack('<4s4H2LH',raw[-22:]));tail[3]=tail[4]=1
            p.write_bytes(raw[:-22]+struct.pack('<4s4H2LH',*tail))
            with patch.object(c,'MAX_FILES',1):v.directory_admission(p)
            with zipfile.ZipFile(p) as z:self.assertEqual(len(z.infolist()),3)

    def test_extracted_corruption_accepted(self):
        fixture=fixtures.Tests();fixture.setUp()
        try:
            fixture.create();name,h=fixture.auth('VERIFY_EXTRACT','extract')
            original=c.Reader.end
            target=fixture.root/'extract/payload/evidence/proof.txt'
            def corrupt(rd):
                target.write_bytes(b'not the verified source bytes')
                return original(rd)
            with patch.object(c.Reader,'end',corrupt):result=v.run(fixture.root,name,h,'extract')
            self.assertEqual(result['status'],'VERIFIED_STREAMED_EVIDENCE')
            self.assertNotEqual(target.read_bytes(),(fixture.root/'proof.txt').read_bytes())
        finally:fixture.tearDown()

    def test_payload_overwrites_authenticated_source_pin(self):
        fixture=fixtures.Tests();fixture.setUp()
        try:
            source=fixture.root/'write_evidence.py';old=source.read_bytes();new=b'X'*len(old)
            fixture.sel['files']=[dict(source='write_evidence.py',target='historical/source.py',sha256=c.digest(new),bytes=len(new))]
            fixture.put('selection.json',fixture.sel);name,h=fixture.auth()
            original=zipfile.ZipFile.writestr
            def mutate(z,*args,**kwargs):
                result=original(z,*args,**kwargs);source.write_bytes(new);return result
            with patch.object(zipfile.ZipFile,'writestr',mutate):result=w.run(fixture.root,name,h,'create')
            self.assertEqual(result['status'],'CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING')
            self.assertEqual(result['source_pins']['write_evidence.py'],c.digest(old))
            self.assertNotEqual(c.digest(source.read_bytes()),result['source_pins']['write_evidence.py'])
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
