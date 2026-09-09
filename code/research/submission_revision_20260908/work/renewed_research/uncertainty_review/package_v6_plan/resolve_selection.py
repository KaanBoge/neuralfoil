"""Metadata/source-only finite selection successor; never open a science payload."""
import hashlib,json
from pathlib import Path
import stream_common as c
HERE=Path(__file__).resolve().parent
PROJECT=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
OWN=HERE.relative_to(PROJECT).as_posix()
ED='submission_revision_20260908/renewed_manuscript_v9/'
TOOLS='submission_revision_20260908/work/renewed_research/independent_environment/final_qa_tools/'
def metadata(p,h):
    b=p.read_bytes()
    if c.digest(b)!=h:raise ValueError('fixed metadata SHA')
    return c.parse(b)
def run():
    proposal=metadata(HERE/'INVENTORY_PROPOSAL.json','79fb68943cc5f23f9219f9dff06efe9bdc8ef1b435a879eadb3b07c0e723ec68')
    resolution=metadata(HERE/'SOURCE_ALIAS_RESOLUTION.json','69f2a9f97ea15707712efda9adad225da938c9e26984ad148efb549c73256b87')
    rows={};substitutions=[]
    aliases={r['original_path'] for r in resolution['bindings']}
    def add(source,h,size=None):
        c.allowed(source);c.pin(h);p=c.path(PROJECT,source)
        n=p.stat().st_size
        if size is not None and size!=n:raise ValueError('stat changed '+source)
        if source in rows and rows[source]['sha256']!=h:raise ValueError('unresolved source alias '+source)
        rows[source]={'source':source,'target':'project/'+source,'sha256':h,'bytes':n}
    for r in proposal['addon_files']:
        if r['source'] in aliases:continue
        add(r['source'],r['sha256'],r['bytes'])
    for item in resolution['bindings']:
        r=item['resolution'];substitutions.append(item)
        if r['kind']=='preserved_source_tar_member':add(r['source'],r['archive_sha256'])
        elif r['kind']=='current_source_file':add(r['source'],r['sha256'],r['bytes'])
        else:raise ValueError('resolution kind')
    for n,h in [
      (ED+'work/FINAL_TECHNICAL_QA_v9.json','24282221edca95bfefe05e2add3f5974e49c406d6d68565d421f5faabb1bcc26'),
      (ED+'work/ROOT_FINAL_QA_CONFIG_v2.json','419e75ceec4cf80b364572f0e776a40f2d6506a90178f79b794ad8b42a510642')]:metadata(PROJECT/n,h);add(n,h)
    # Only these bounded authoring source bodies are read to establish new pins.
    for n in ['finalize_v9_v2.py','test_finalize_v9_v2.py']:
        p=PROJECT/TOOLS/n;add(TOOLS+n,c.digest(p.read_bytes()))
    for n in ['SOURCE_ALIAS_RESOLUTION.json','resolve_snapshots.py','CLOSURE_SCOPE.md']:
        p=HERE/n;add(OWN+'/'+n,c.digest(p.read_bytes()))
    excluded=[r for r in proposal['unresolved_schema_records'] if 'external_runtime_not_packaged' in r]
    lineage={'status':'RESOLVED_SAVED_EVIDENCE_SELECTION_NO_PAYLOAD_READ','proposal_sha256':'79fb68943cc5f23f9219f9dff06efe9bdc8ef1b435a879eadb3b07c0e723ec68','source_alias_resolution_sha256':'69f2a9f97ea15707712efda9adad225da938c9e26984ad148efb549c73256b87','source_substitutions':substitutions,'external_runtime_exclusions':excluded,'legacy_archive_paths_unchanged':True,'science_payloads_opened':False,'new_portable_pipeline_claim':False}
    lp=HERE/'SELECTION_LINEAGE.json';raw=c.encode(lineage)
    with lp.open('xb') as f:f.write(raw)
    add(OWN+'/'+lp.name,c.digest(raw))
    selection={'schema':'v9-evidence-selection-1','claim':'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE','unresolved':[],'closure_review':{'source':OWN+'/CLOSURE_SCOPE.md','sha256':c.digest((HERE/'CLOSURE_SCOPE.md').read_bytes())},'files':sorted(rows.values(),key=lambda r:r['target'])}
    c.records(selection);raw=c.encode(selection)
    with (HERE/'EVIDENCE_SELECTION_v1.json').open('xb') as f:f.write(raw)
    print({'status':'SOURCE_SELECTION_ONLY_NO_EXPORT','files':len(rows),'bytes':sum(r['bytes'] for r in rows.values()),'selection_sha256':c.digest(raw),'external_runtime_exclusion_occurrences':len(excluded),'source_alias_bindings':len(substitutions)})
if __name__=='__main__':run()
