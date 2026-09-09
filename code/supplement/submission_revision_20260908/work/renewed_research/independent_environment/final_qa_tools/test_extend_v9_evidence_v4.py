import copy,unittest
import extend_v9_evidence_v4 as x
class Fake:
    def __init__(self):
        self.evidence=[];self.reads={}
        self.d={'status':'PASS_INDEPENDENT_SAVED_DISPLAY','differences':[],'fits':0,'resampling':0,'manifest_sha256':'a'*64,'binding_sha256':'50d47f6464353f485d9e74f28e212f5502ec11608334edcfc1d3dae54941765a','source_sha256':'b'*64}
    def obj(self,*args):return self.d
    def entry(self,role,path,*args):
        e={'role':role,'path':path};self.evidence.append(e);return e
    def maps(self,*args):pass
    def scalar(self,*args):pass
class Tests(unittest.TestCase):
    def base(self):return {'added_evidence':[{'role':'four_tree_displays','sha256':'a'*64}],'pending_roles':[{'role':'four_display_independent_review','reason':'pending'},{'role':'v9_assembly','reason':'pending'}],'authenticated_metadata_and_source_sha256':{},'legacy_evidence_unmodified':[{'role':'unchanged'}],'legacy_old_qa_unmodified':{},'history_pins':[]}
    def test_append_only(self):
        b=self.base();before=copy.deepcopy(b);v=x.extend(b,Fake())
        self.assertEqual(b,before);self.assertEqual(v['added_evidence'][:1],b['added_evidence']);self.assertEqual(v['legacy_evidence_unmodified'],b['legacy_evidence_unmodified'])
        self.assertEqual(v['pending_roles'],[{'role':'v9_assembly','reason':'pending'}])
    def test_bad_or_failed_audit(self):
        for key,value in [('status','FAILURE'),('manifest_sha256','c'*64),('differences',[1]),('fits',1)]:
            f=Fake();f.d[key]=value
            with self.assertRaises(ValueError):x.extend(self.base(),f)
    def test_scaffold_never_authorized(self):
        b=self.base();legacy={'documents':{k:{'source':{'path':'fixture','sha256':'a'*64}} for k in ['main','supplement']}}
        d=x.scaffold(b,legacy)
        self.assertIs(d['finalization_authorized'],False)
        self.assertEqual(d['content_contract']['references'],23)
        for v in d['documents'].values():
            self.assertIsNone(v['version']);self.assertIsNone(v['visual']);self.assertIsNone(v['pdf'])
if __name__=='__main__':unittest.main()
