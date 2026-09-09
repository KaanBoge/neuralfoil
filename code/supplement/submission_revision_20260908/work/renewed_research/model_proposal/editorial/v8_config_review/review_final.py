"""Read-only final receipt and actual TOC audit. No finalizer imports."""
from pathlib import Path
import hashlib,json,zipfile,xml.etree.ElementTree as E
R=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper');D=R/'submission_revision_20260908/renewed_manuscript_v8'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check(p,h):
 p=Path(p);p=p if p.is_absolute() else D/p
 assert not any(v.is_symlink() for v in [p,*p.parents]);assert p.resolve().is_relative_to(R)
 assert sha(p)==h,str(p)
 return p
qpath=check(D/'work/FINAL_TECHNICAL_QA.json','ac58346bdc55f51370197788354319ead001f4ae0cbe90ea810b693f3c6fe2b7');q=json.loads(qpath.read_bytes())
assert q['status']=='PASS_TECHNICAL_PREPARATION' and len(q['files'])==1432
for name,h in q['files'].items():check(name,h)
cp=check(q['config_path'],q['config_sha256']);c=json.loads(cp.read_bytes());assert c['finalization_authorized'] is True
assert q['config_sha256']=='8f5ca571dc86f17091dee5a2d8b05b2ef1f677e186618bef0032a928f82f70f3'
old=json.loads((D/'work/ROOT_FINAL_QA_CONFIG_FINAL_v1.json').read_bytes())
for k,d in c['documents'].items():
 for field in ['source','builder','build','layout','page_map','docx','pdf','visual']:assert d[field]==old['documents'][k][field],(k,field)
 for a in q['documents'][k]['artifacts'].values():check(a['path'],a['sha256'])
s=c['documents']['supplement'];pm=json.loads((R/s['page_map']['path']).read_bytes())
x=E.fromstring(zipfile.ZipFile(R/s['docx']['path']).read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
paras=[]
for p in x.findall('./w:body/w:p',ns):
 paras.append(''.join(('\t' if n.tag=='{'+ns['w']+'}tab' else n.text or '' if n.tag=='{'+ns['w']+'}t' else '') for run in p.findall('.//w:r',ns) for n in run.iter()))
for heading,label in s['toc_labels'].items():assert label+'\t'+str(pm[heading]) in paras,(heading,label)
a=(D/'supplement.reading.md').read_bytes();b=(D/'supplement.reading.v2.md').read_bytes()
assert b==a.replace(b'| S9 Incremental harm calibration | 63 |',b'| S9 Harm calibration and confidence comparisons | 63 |') and a!=b
assert sha(D/'supplement.reading.v2.md')=='091212b7e29bee61885b12e7a3fb5f40fd186e1959b066c14ce47ede97b912f3'
for name,h in q['files'].items():check(name,h)
result={'status':'PASS_ACTUAL_FINAL_RECEIPT_AND_CORRECTED_TOC_REVIEW','qa_sha256':sha(qpath),'config_sha256':sha(cp),'finalizer_rerun':False,'actual_qa_files_reauthenticated':1432,'prior_independent_union_files':1801,'scope_difference':'Actual finalizer finite receipt inventory versus earlier broader independent evidence/old-QA/page pin union; no equality assumed.','render_source_visual_config_fields_unchanged':True,'all_toc_labels_docx_checked':12,'only_reading_S9_line_changed':True,'old_scientific_files':q['old_scientific_files'],'old_total_files':q['old_total_files'],'first_failure_preserved':sha(D/'work/FINALIZATION_ATTEMPT_1.md'),'review_source_sha256':sha(Path(__file__)),'guide_pins':{p.name:sha(p) for p in sorted((D/'work/package_documents').glob('*.md'))}}
with (Path(__file__).parent/'FINAL_RECEIPT_REVIEW.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
