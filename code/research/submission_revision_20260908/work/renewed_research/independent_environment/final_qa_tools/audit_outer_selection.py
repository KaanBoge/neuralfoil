"""Actual outer selection audit: finite metadata/source reads, payload STAT only."""
import collections,hashlib,json
from pathlib import Path
P=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
B=P/'submission_revision_20260908/work/renewed_research/uncertainty_review/package_v6_plan'
E='submission_revision_20260908/renewed_manuscript_v9'
READS={}
def raw(p,h=None):
    b=p.read_bytes();v=hashlib.sha256(b).hexdigest()
    if h is not None:assert v==h,str(p)
    READS[str(p)]=v;return b
def obj(p,h=None):return json.loads(raw(p,h))
def main():
    s=obj(B/'OUTER_SELECTION_v1.json','6b5cdd33dab3ec0859632c1fee32b36b30949f1f006cc8755f4739356643e2d4')
    a=obj(B/'ROOT_OUTER_SELECTION_APPROVAL_v1.json','caf18678183807a80b3f2f4a46bf5d5d8fcf901ab6eeee6d24301e1368eb0403')
    proposal=obj(B/'ROOT_OUTER_SELECTION_APPROVAL_PROPOSAL_v1.json')
    assert a['phase']=='METADATA_SELECTION_ONLY' and proposal['phase']=='PROPOSAL_ONLY_NOT_AUTHORIZED'
    assert {k:v for k,v in a.items() if k not in {'phase','provenance'}}=={k:v for k,v in proposal.items() if k not in {'phase','provenance'}}
    assert len(proposal['provenance'])==68 and len(a['provenance'])==72
    assert all(r in a['provenance'] for r in proposal['provenance'])
    extra=[r for r in a['provenance'] if r not in proposal['provenance']]
    assert len(extra)==4
    rows=s['files'];targets={r['target']:r for r in rows};roles=collections.Counter(r['role'] for r in rows)
    assert len(rows)==len(targets)==540 and sum(r['bytes'] for r in rows)==378482698
    assert s['schema']=='v6-resolved-selection-1' and s['unresolved']==[]
    assert s['claim']=='SAVED_EVIDENCE_AND_UNCHANGED_LEGACY_REPLAYS_NOT_NEW_PORTABLE_PIPELINE'
    for r in rows:
        p=P/r['source'];assert p.is_file() and not any(q.is_symlink() for q in (p,*p.parents))
        assert p.stat().st_size==r['bytes']
    d={k:obj(P/v['source'],v['sha256']) for k,v in a['inputs'].items() if k!='archive'}
    qa=d['qa'];cfg=d['config'];qmap={str((P/E/n).resolve().relative_to(P)):h for n,h in qa['files'].items() if (P/E/n).resolve().is_relative_to(P)}
    assert qa['status']=='PASS_TECHNICAL_PREPARATION' and qa['config_sha256']==a['inputs']['config']['sha256']
    assert qa['external_readonly_files']==cfg['external_readonly_pins'] and len(qa['external_readonly_files'])==360
    assert len(qa['review_files'])==roles['review']==8
    for key in qa['review_files']:
        source=str((P/E/key).resolve().relative_to(P));r=targets['quality/reviews/'+key.replace('../','parent/')]
        assert r['source']==source and r['sha256']==qmap[source] and r['qa_key']==key
    for kind in ['main','supplement']:
        artifacts=qa['documents'][kind]['artifacts']
        for ext,key in [('pdf','pdf'),('docx','docx'),('md','reading_source' if kind=='supplement' else 'source')]:
            r=targets['manuscript/'+kind+'.'+ext];art=artifacts[key]
            assert (P/r['source']).resolve()==Path(art['path']).resolve() and r['sha256']==art['sha256']==qmap[r['source']]
    assert roles['figure']==18 and roles['source_image_alias']==6
    for r in rows:
        if r['role'] in {'figure','source_image_alias'}:assert qmap[r['source']]==r['sha256']
    for n,h in a['guide_pins'].items():
        target=('author_approval/' if n=='AUTHOR_CHECKLIST.md' else '')+n
        r=targets[target];assert r['source']==E+'/work/package_documents/'+n and r['sha256']==h
        raw(P/r['source'],h)
    for spec in a['provenance']:
        r=targets[spec['target']]
        assert all(r[k]==spec[k] for k in spec) and r['role']=='package_provenance'
        raw(P/spec['source'],spec['sha256'])
    for n,h in a['source_pins'].items():raw(P/n,h)
    for n,h in a['required_source_pins'].items():raw(P/n,h)
    for n,h in a['helper_pins'].items():raw(P/E/'work/package_documents'/n,h)
    old='submission_revision_20260908/renewed_manuscript_v8/deliverables/NeuralFoil_Private_Submission_Package_v5'
    oi=obj(P/old/'INPUT_MANIFEST.json','0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8')
    archives=[r for r in rows if r['role']=='private_archive'];assert len(archives)==9
    for r in archives:
        if r['id']=='v9_evidence':
            assert r['source']==a['inputs']['archive']['source'] and r['sha256']==a['inputs']['archive']['sha256']
        else:
            oldrow=next(x for x in oi['files'] if x.get('id')==r['id'] and x['role']=='private_archive')
            assert r['source']==old+'/'+oldrow['target'] and (r['sha256'],r['bytes'])==(oldrow['sha256'],oldrow['bytes'])
    assert roles['package_provenance']==72 and 460+8+72==len(rows)
    ia=obj(B/'ROOT_INVENTORY_APPROVAL_v1.json','f630750f19aa90c0c8267ed59ac80624be29bf7211b83b1b113b60a8c29c0041')
    im=obj(B/'INPUT_MANIFEST_v6.json','1cbc550dcd5ee6fab83de13a61896582c2b89a3101af034a10f30f55e37a21f0')
    assert ia['authorized_phase']=='PREPARE_INVENTORY_ONLY' and ia['selection_sha256']==READS[str(B/'OUTER_SELECTION_v1.json')]
    assert ia['human_author_approval'] is False and ia['public_release'] is False
    assert im['files']==rows and im['requirements']==s['requirements']
    assert im['qa_binding']=={'edition':E,**a['inputs']['qa']}
    assert im['legacy_witness']=={'source':old+'/MANIFEST.json','sha256':'9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9'}
    assert im['schema']=='private_submission_inputs_v4' and im['wire_format_version']==4 and im['package_revision']==6 and im['manuscript_edition']=='V9'
    assert im['human_author_approval'] is False and im['public_release'] is False and im['max_payload_bytes']==536870912
    return {'status':'PASS_METADATA_SOURCE_ONLY','rows':540,'stat_bytes':378482698,'roles':dict(roles),
      'old_provenance_preserved':68,'extra_provenance':extra,'qa_reviews':8,'external_pins_preserved_not_payload':360,
      'archives':[{k:r[k] for k in ['id','source','target','sha256','bytes']} for r in archives],
      'input_manifest_exact_selection_and_requirements':True,
      'metadata_source_sha256':READS,'scientific_payloads_read':False,'outer_inventory_or_assembly_run':False}
if __name__=='__main__':print(json.dumps(main(),indent=2))
