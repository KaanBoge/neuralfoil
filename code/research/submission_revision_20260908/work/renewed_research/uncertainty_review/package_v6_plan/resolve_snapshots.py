"""Read only two explicit source TARs; resolve known historical source aliases."""
import hashlib,json,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROJECT=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
BASE=Path('submission_revision_20260908/work/renewed_research/model_proposal/four_tree_matching_plan/all_context_proposal/implementation')
NAMES={'HANDOFF.md','context_support.py','entry.py','prepare_freeze.py','test_contexts.py'}
def sha(b):return hashlib.sha256(b).hexdigest()
def run():
    raw=(HERE/'INVENTORY_PROPOSAL.json').read_bytes();d=json.loads(raw)
    occurrences=[r for r in d['unresolved_schema_records'] if 'historical_source_needs_snapshot' in r]
    wanted={(r['historical_source_needs_snapshot'],r['sha256']) for r in occurrences}
    # The first/retained version of the same aliases must also resolve.
    for r in d['addon_files']:
        if Path(r['source']).parent==BASE and Path(r['source']).name in NAMES:wanted.add((r['source'],r['sha256']))
    candidates={};archives={}
    for filename in ['SOURCE_V1_PRESERVED.tar','SOURCE_V2_PRESERVED.tar']:
        p=PROJECT/BASE/filename;b=p.read_bytes();archives[str(BASE/filename)]=sha(b)
        with tarfile.open(p,'r:') as t:
            names=t.getnames()
            if len(names)!=len(set(names)):raise ValueError('duplicate TAR source')
            for name in sorted(NAMES):
                member=t.getmember(name)
                if not member.isfile() or member.size>1024*1024:raise ValueError('source member type/size')
                body=t.extractfile(member).read();h=sha(body)
                candidates[(str(BASE/name),h)]={'kind':'preserved_source_tar_member','source':str(BASE/filename),'archive_sha256':archives[str(BASE/filename)],'member':name,'sha256':h,'bytes':len(body)}
    for name in sorted(NAMES):
        p=PROJECT/BASE/name;b=p.read_bytes();h=sha(b)
        candidates[(str(BASE/name),h)]={'kind':'current_source_file','source':str(BASE/name),'sha256':h,'bytes':len(b)}
    missing=wanted-candidates.keys()
    if missing:raise ValueError('unresolved exact source '+repr(missing))
    result={'status':'SOURCE_ALIASES_RESOLVED_NO_EVIDENCE_EXPORT','proposal_sha256':sha(raw),'conflict_occurrences':len(occurrences),'unique_conflicts':len({(r['historical_source_needs_snapshot'],r['sha256']) for r in occurrences}),'all_versioned_source_bindings':len(wanted),'source_archives':archives,'bindings':[{'original_path':p,'expected_sha256':h,'resolution':candidates[p,h]} for p,h in sorted(wanted)],'scientific_payloads_read':False,'archives_created':False}
    with (HERE/'SOURCE_ALIAS_RESOLUTION.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print({k:v for k,v in result.items() if k!='bindings'})
if __name__=='__main__':run()
