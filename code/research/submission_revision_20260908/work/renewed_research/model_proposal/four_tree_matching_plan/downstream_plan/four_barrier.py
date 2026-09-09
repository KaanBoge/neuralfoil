"""No numerical model execution. Strict future sixteen-context receipt barrier."""
from pathlib import Path
from fractions import Fraction

def digest(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def relative(value):
    p=Path(value)
    if p.is_absolute() or '..' in p.parts:raise ValueError('finite relative path')
    return p
def validate_registry(reg):
    f=reg['four_tree']
    if set(f)!={'root','registry_sha256','producer_sha256','replay_sha256','producer_approval_sha256','replay_approval_sha256','context_support_sha256'}:raise ValueError('explicit future four-tree barrier schema')
    if f['root']!='model_proposal/four_tree_matching_plan/all_context_proposal/implementation':raise ValueError('fixed four-tree root')
    if not all(digest(v) for k,v in f.items() if k!='root'):raise ValueError('missing actual barrier pin; no freeze')
    p=reg['paired_results']
    if p['root']!='model_proposal/paired_tree_plan/all_context_downstream_plan' or not digest(p['registry_sha256']):raise ValueError('paired results root/registry')
    if set(p['phases'])!={'preflight','calibrate','score','assess'}:raise ValueError('complete paired phase chain')
    for value in p['phases'].values():
        if set(value)!={'complete_sha256','approval_sha256','approval_path'} or not digest(value['complete_sha256']) or not digest(value['approval_sha256']):raise ValueError('paired phase explicit pins')
        relative(value['approval_path'])
def fraction(v):
    if type(v)!=dict or set(v)!={'encoding','numerator','denominator'} or v['encoding']!='signed_hex_fraction_v1':raise ValueError('exact rational schema')
    n=int(v['numerator'],16);d=int(v['denominator'],16)
    if d<=0 or hex(n)!=v['numerator'] or hex(d)!=v['denominator']:raise ValueError('canonical signed hex')
    f=Fraction(n,d)
    if f.numerator!=n or f.denominator!=d:raise ValueError('reduced fraction required')
    return f
def compare(summary,paired):
    for k in ['lower','upper','B']:
        if fraction(summary['original_adjacent'][k])!=fraction(paired['D'][k]):raise ValueError('exact paired predecessor comparison')
    b=fraction(summary['final']['B']);pb=fraction(summary['original_adjacent']['B']);sb=fraction(summary['stage0']['B'])
    if not 0<=b<=pb<=sb:raise ValueError('bound nesting')
    return summary
def authenticate(reg,root,read,json_read,ledger,contexts,paired,modules):
    f=reg['four_tree'];path=root/f['root']
    cr=json_read(path/'REGISTRY_v3.json',f['registry_sha256'],ledger)
    specs={'four_context_support':(path/'context_support.py',f['context_support_sha256'])}
    if cr['sources']['context_support.py']!=f['context_support_sha256']:raise ValueError('certificate source pin')
    result={}
    with modules(specs,ledger) as loaded:
        s=loaded['four_context_support'];s.authenticate(cr,f['registry_sha256'],ledger)
        if s.CONTEXTS!=contexts or [r['context'] for r in cr['contexts']]!=contexts:raise ValueError('sixteen ordered models')
        produced=None;produced_children={}
        for phase,key in [('certificates_produce','producer'),('certificates_replay','replay')]:
            ap=json_read(path/('ROOT_'+phase.upper()+'_APPROVAL.json'),f[key+'_approval_sha256'],ledger);s.strict_approval(ap,f['registry_sha256'],phase)
            record=json_read(path/phase/'COMPLETE.json',f[key+'_sha256'],ledger)
            if record.get('status')!='COMPLETE' or record.get('phase')!=phase or record.get('registry_sha256')!=f['registry_sha256'] or record.get('approval_sha256')!=f[key+'_approval_sha256'] or set(record['contexts'])!=set(contexts):raise ValueError('aggregate complete barrier')
            if record['fresh_contexts']!=15 or record['inherited_contexts']!=1 or record['fits']!=0 or record['features_targets_loaded']!=0 or record['R_used'] is not False:raise ValueError('certificate scope')
            s.verify_outputs(path/phase,record,ledger)
            if key=='replay' and (ap['producer_complete_sha256']!=f['producer_sha256'] or record['producer_complete_sha256']!=f['producer_sha256']):raise ValueError('replay predecessor')
            for ctx,row in zip(contexts,cr['contexts']):
                e=record['contexts'][ctx]
                if ctx=='final':
                    if e!=s.inherited(cr,ledger) or e['model_sha256']!=row['model_sha256']:raise ValueError('inherited final identity')
                    summary=e['summary']
                else:
                    child=json_read(path/phase/ctx/'COMPLETE.json',e['complete_sha256'],ledger);s.verify_outputs(path/phase/ctx,child,ledger)
                    if child.get('status')!='COMPLETE' or child['context']!=ctx or child['phase']!=phase or child['registry_sha256']!=f['registry_sha256'] or child['approval_sha256']!=f[key+'_approval_sha256'] or child['model_sha256']!=row['model_sha256'] or child['summary']!=e['summary']:raise ValueError('context complete/model binding')
                    summary=child['summary']
                    if key=='producer':produced_children[ctx]=child
                    if key=='replay' and (summary['producer_complete_sha256']!=produced['contexts'][ctx]['complete_sha256'] or summary['certificate_sha256']!=produced_children[ctx]['outputs']['certificate.json']):raise ValueError('child replay predecessor/certificate')
                compare(summary,paired['summary']['contexts'][ctx]['summary'])
                if key=='replay':
                    for k in ['stage0','original_adjacent','final','counts']:
                        if summary[k]!=produced['contexts'][ctx]['summary'][k]:raise ValueError('independent replay result mismatch')
                    result[ctx]={'summary':summary,'model_sha256':row['model_sha256']}
            if key=='producer':produced=record
        s.authenticate(cr,f['registry_sha256'],ledger)
    return {'summary':{'contexts':result},'four_tree_registry_sha256':f['registry_sha256'],'paired_predecessor':paired}
