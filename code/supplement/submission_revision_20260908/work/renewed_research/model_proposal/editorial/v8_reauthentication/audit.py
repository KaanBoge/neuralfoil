"""Read-only V8 editorial/source reauthentication; no assembly or scientific execution."""
import datetime,difflib,hashlib,json,re
from pathlib import Path
ROOT=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
HERE=Path(__file__).resolve().parent
V8=ROOT/'submission_revision_20260908/renewed_manuscript_v8'
U=ROOT/'submission_revision_20260908/work/renewed_research/uncertainty_review'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def read(p):return p.read_text()
def tables(s):return re.findall(r'(?:^\|.*\n)+',s,re.M)
def refs(s):return {int(k):v.strip() for k,v in re.findall(r'^\[(\d+)\] (.*?)(?=\n\n\[|\Z)',s.split('# References',1)[1],re.M|re.S)}
def section(s,begin,end):return s.split(begin,1)[1].split(end,1)[0]
def write(p,x):
    raw=json.dumps(x,indent=2,sort_keys=True,allow_nan=False).encode()
    with p.open('xb') as f:f.write(raw)
def main():
    current={'main.complete.md':'768ffc2a37b7ecae4e644fa00a04a367c2e86868f1ff2981a6b700f843a8357e','supplement.complete.md':'cd1fd7942bd7dbf1881a6012d8c90de5726315f45d0c97b7651e0bf709c81157','work/ASSEMBLY.json':'8d3517f09f2dc1044baf388d9e2a96fe352873aebbbdca8e0443d008da29c373'}
    prior=json.loads(read(U/'V8_ASSEMBLY_QA.json'))
    assert prior['status']=='PASS_ASSEMBLED_SOURCE_TABLE_AUDIT'
    history={'main.complete.md':V8/'work/render_main/v1/main.complete.md','supplement.complete.md':V8/'work/render_supplement/v1/supplement.complete.md','work/ASSEMBLY.json':V8/'work/render_main/v1/ASSEMBLY.json'}
    for key,p in history.items():assert sha(p)==prior['source_hashes'][key],key
    for key,pin in current.items():assert sha(V8/key)==pin,key
    m=json.loads(read(V8/'work/ASSEMBLY.json'));assert m['status']=='PASS' and m['references']==21
    assert m['main_sha256']==current['main.complete.md'] and m['supplement_sha256']==current['supplement.complete.md']
    checked={}
    for name,pin in m['source_sha256'].items():
        p=ROOT/name;assert p.resolve().is_relative_to(ROOT) and sha(p)==pin,name;checked[name]=pin
    assert sha(V8/'assemble_submission.py')==m['code_sha256']
    checked[rel(V8/'assemble_submission.py')]=m['code_sha256']
    a,b=read(V8/'main.complete.md'),read(V8/'supplement.complete.md')
    oa,ob=read(history['main.complete.md']),read(history['supplement.complete.md'])
    assert tables(a)==tables(oa) and len(tables(a))==4
    assert tables(b)==tables(ob) and len(tables(b))==36
    assert re.findall(r'^Table S(\d+)\.',b,re.M)==[str(i) for i in range(1,36)]
    assert refs(a)==refs(b)==refs(oa)==refs(ob) and set(refs(a))==set(range(1,22))
    # Exact changed-block inventory: three replacements in main, one insertion in supplement.
    changes={}
    for name,old,new in [('main',oa,a),('supplement',ob,b)]:
        oldlines=old.splitlines(keepends=True);newlines=new.splitlines(keepends=True)
        delta=[]
        for tag,i,j,k,l in difflib.SequenceMatcher(None,oldlines,newlines,autojunk=False).get_opcodes():
            if tag!='equal':delta.append({'tag':tag,'old_start_1':i+1,'old_end_exclusive_1':j+1,'new_start_1':k+1,'new_end_exclusive_1':l+1,'old_text':''.join(oldlines[i:j]),'new_text':''.join(newlines[k:l])})
        changes[name]=delta
    assert [c['tag'] for c in changes['supplement']]==['insert']
    assert changes['main'][0]['old_start_1']==8 and changes['main'][1]['old_start_1']==16
    reproduction='## Reproducibility and the scope of verification'
    oldrep=section(oa,reproduction,'# 6 Discussion');newrep=section(a,reproduction,'# 6 Discussion')
    moved=oldrep.strip().split('\n\n',1)[0]
    assert changes['supplement'][0]['new_text'].strip()==moved
    assert moved not in a and b.count(moved)==1 and moved not in ob
    # Removing only the three explicitly inspected sections proves all other main bytes identical.
    def masked(s):
        s=s.replace(section(s,'# Abstract','Keywords:'),'[ABSTRACT]\n')
        paras=s.splitlines(keepends=True)
        para=next(x for x in paras if x.startswith('A measurement-informed correction addresses'))
        s=s.replace(para,'[CORRECTION_EXPLANATION]\n')
        return s.replace(section(s,reproduction,'# 6 Discussion'),'[REPRODUCTION]\n')
    assert masked(a)==masked(oa)
    assert b.replace(changes['supplement'][0]['new_text'],'',1)==ob
    assert '[20]' in newrep and 'Verification establishes' in newrep
    source_pins={**checked,**{rel(V8/key):pin for key,pin in current.items()},rel(U/'V8_EDITORIAL_DELTA_REVIEW.md'):sha(U/'V8_EDITORIAL_DELTA_REVIEW.md')}
    historical_pins={rel(p):sha(p) for p in history.values()};historical_pins[rel(U/'V8_ASSEMBLY_QA.json')]=sha(U/'V8_ASSEMBLY_QA.json')
    result={'status':'PASS_CURRENT_V8_EDITORIAL_ASSEMBLY_REAUTHENTICATION','created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'main_tables':4,'supplement_markdown_blocks':36,'supplement_numbered_tables':35,'references':21,
      'all_tables_byte_unchanged':True,'all_references_unchanged':True,'main_changed_blocks':3,'supplement_changed_blocks':1,'main_diff_opcode_count':len(changes['main']),
      'two_editorial_clarifications_exactly_localized':True,'reproduction_section_condensed_as_documented':True,'detailed_replay_paragraph_moved_verbatim':True,
      'all_other_main_bytes_unchanged':True,'all_other_supplement_bytes_unchanged':True,'visual_review_performed':False,'scientific_execution_performed':False,
      'source_sha256':source_pins,'historical_source_sha256':historical_pins,'script_sha256':sha(Path(__file__)),
      'changed_blocks':changes,'main_block_count_semantics':'three anchored editorial regions, not difflib opcode count','preserved_harness_failure_sha256':sha(HERE/'FIRST_ATTEMPT.md'),'historical_review_is_not_rebound_to_current_files':True,'assembly_input_count':len(m['source_sha256'])}
    write(HERE/'CURRENT_V8_QA.json',result)
    config={'status':'DRAFT_ROOT_SELECTION_REQUIRED','finalization_authorized':False,'evidence':[
      {'role':'assembly','path':rel(V8/'work/ASSEMBLY.json'),'sha256':current['work/ASSEMBLY.json'],'assertions':[{'pointer':'/status','equals':'PASS'},{'pointer':'/references','equals':21}],'maps':[{'pointer':'/source_sha256','base':'.'}],'scalar_pins':[{'pointer':'/code_sha256','path':rel(V8/'assemble_submission.py')},{'pointer':'/main_sha256','path':rel(V8/'main.complete.md')},{'pointer':'/supplement_sha256','path':rel(V8/'supplement.complete.md')}]},
      {'role':'assembly_audit','path':rel(HERE/'CURRENT_V8_QA.json'),'sha256':sha(HERE/'CURRENT_V8_QA.json'),'assertions':[{'pointer':'/status','equals':result['status']},{'pointer':'/all_tables_byte_unchanged','equals':True},{'pointer':'/references','equals':21},{'pointer':'/visual_review_performed','equals':False}],'maps':[{'pointer':'/source_sha256','base':'.'},{'pointer':'/historical_source_sha256','base':'.'}],'scalar_pins':[{'pointer':'/script_sha256','path':rel(Path(__file__))}]},
      {'role':'editorial_delta','path':rel(HERE/'CURRENT_V8_QA.json'),'sha256':sha(HERE/'CURRENT_V8_QA.json'),'assertions':[{'pointer':'/main_changed_blocks','equals':3},{'pointer':'/supplement_changed_blocks','equals':1},{'pointer':'/detailed_replay_paragraph_moved_verbatim','equals':True},{'pointer':'/all_other_main_bytes_unchanged','equals':True}]}]}
    write(HERE/'FINALIZER_ROLE_DRAFT.json',config)
    print(json.dumps({'QA_sha256':sha(HERE/'CURRENT_V8_QA.json'),'config_draft_sha256':sha(HERE/'FINALIZER_ROLE_DRAFT.json'),'assembly_inputs':len(m['source_sha256'])}))
if __name__=='__main__':main()
