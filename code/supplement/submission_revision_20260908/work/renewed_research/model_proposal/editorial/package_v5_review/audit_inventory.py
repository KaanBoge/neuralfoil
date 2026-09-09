"""Read-only finite payload identity audit; no archive or scientific parsers."""
from pathlib import Path,PurePosixPath
import hashlib,json,collections,stat
R=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper');D=R/'submission_revision_20260908/renewed_manuscript_v8'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def checked(name,h):
 p=R/name
 assert not any(x.is_symlink() for x in [p,*p.parents]);assert p.resolve().is_relative_to(R) and stat.S_ISREG(p.stat().st_mode)
 assert sha(p)==h,str(p)
 return p
p=D/'work/PRIVATE_PACKAGE_V5_INPUTS.json';expected='0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8';assert sha(p)==expected;m=json.loads(p.read_bytes())
assert m['human_author_approval'] is False and m['public_release'] is False and len(m['files'])==432
q=json.loads(checked(m['qa_binding']['source'],m['qa_binding']['sha256']).read_bytes());old=json.loads(checked(m['legacy_witness']['source'],m['legacy_witness']['sha256']).read_bytes())
roles=collections.Counter();names=set();total=0;archives=[];figs=set();reviews=set()
for r in m['files']:
 n=r['target'];parts=PurePosixPath(n).parts
 assert n==str(PurePosixPath(n)) and not n.startswith('/') and '..' not in parts and '\\' not in n and ':' not in n and not any(ord(x)<32 or 127<=ord(x)<=159 for x in n)
 assert n.casefold() not in names;names.add(n.casefold())
 assert not any(x in r['source'].lower() for x in ['all_context','downstream','inference_benchmark','volume4','sealed'])
 for component in Path(r['source']).parts[:-1]:assert not component.startswith(('venv','conda')) and component not in ['.venv','cache','__pycache__','site-packages']
 f=checked(r['source'],r['sha256']);assert f.stat().st_size==r['bytes'];total+=r['bytes'];roles[r['role']]+=1
 if 'qa_key' in r:
  assert q['files'][r['qa_key']]==r['sha256'];assert (D/r['qa_key']).resolve()==f.resolve()
 if r['role']=='review':reviews.add(r['qa_key'])
 if r['role']=='private_archive':
  archives.append(r['id'])
  if 'legacy_member' in r:assert old['files'][r['legacy_member']]['sha256']==r['sha256'] and '/NeuralFoil_Private_Submission_Package_v4/' in r['source']
 if r['role']=='figure':figs.add((r['id'],r['format']))
 if r['role'] in ['main_pdf','main_docx','main_source','supplement_pdf','supplement_docx','supplement_source']:
  k,a=r['role'].split('_',1);a='reading_source' if k=='supplement' and a=='source' else a
  assert q['documents'][k]['artifacts'][a]['sha256']==r['sha256']
assert total==244754847 and total<m['max_payload_bytes']==536870912
assert not names&{'manifest.json','input_manifest.json'} and not any(a!=b and b.startswith(a+'/') for a in names for b in names)
assert reviews==set(q['review_files']) and len(archives)==8 and set(archives)==set(m['requirements']['archive_ids'])
assert len(figs)==18 and roles['source_image_alias']==6
selectionrow=next(r for r in m['files'] if r['role']=='selection_source');s=json.loads((R/selectionrow['source']).read_bytes())
bytarget={r['target']:r for r in m['files']}
for r in s['files']:assert bytarget[r['target']]['sha256']==r['sha256'] and bytarget[r['target']]['source']==r['source']
ar=next(r for r in m['files'] if r['role']=='inventory_authorization');assert ar['sha256']=='52a7006a0e7a4feaa8853b4d65a6da445c1bbdf16ee16fb2b05c336dbd36e880'
a=json.loads((R/ar['source']).read_bytes());assert a['qa_sha256']==m['qa_binding']['sha256'] and (R/a['output']).resolve()==p.resolve()
for r in m['files']:checked(r['source'],r['sha256'])
result={'status':'PASS_ACTUAL_FINITE_INVENTORY_REVIEW_NOT_ASSEMBLY','inventory_sha256':expected,'file_count':432,'payload_bytes':total,'archive_count':8,'legacy_archive_count':sum('legacy_member' in r for r in m['files']),'figure_formats':18,'image_aliases':6,'publication_roles':6,'selection_records':len(s['files']),'roles':dict(roles),'qa_sha256':m['qa_binding']['sha256'],'approval_sha256':ar['sha256'],'scientific_array_parsing':False,'archive_extraction':False,'assembly':False,'end_payload_reauthentication':True,'script_sha256':sha(Path(__file__))}
with (Path(__file__).parent/'INVENTORY_REVIEW.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
