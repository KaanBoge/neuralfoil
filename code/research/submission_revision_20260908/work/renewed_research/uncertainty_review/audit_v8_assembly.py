"""Read-only assembled-source/table audit; no assembly or scientific execution."""
from pathlib import Path
import hashlib,json,re,collections
ROOT=Path(__file__).resolve().parents[4]
V8=ROOT/'submission_revision_20260908/renewed_manuscript_v8'
V7=ROOT/'submission_revision_20260908/renewed_manuscript_v7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tables(s):return re.findall(r'(?:^\|.*\n)+',s,re.M)
def refs(s):return {int(k):v.strip() for k,v in re.findall(r'^\[(\d+)\] (.*?)(?=\n\n\[|\Z)',s.split('# References',1)[1],re.M|re.S)}
def main():
    out=Path(__file__).with_name('V8_ASSEMBLY_QA.json')
    if out.exists():raise FileExistsError(out)
    manifest=json.loads((V8/'work/ASSEMBLY.json').read_text())
    for p,pin in manifest['source_sha256'].items():assert sha(ROOT/p)==pin,p
    assert sha(V8/'assemble_submission.py')==manifest['code_sha256']
    a=(V8/'main.complete.md').read_text();b=(V8/'supplement.complete.md').read_text()
    assert sha(V8/'main.complete.md')==manifest['main_sha256'] and sha(V8/'supplement.complete.md')==manifest['supplement_sha256']
    olda=(V7/'main.complete.md').read_text();oldb=(V7/'supplement.complete.md').read_text()
    ta,tb,oa,ob=map(tables,(a,b,olda,oldb));q=V8/'work/qualified_displays'
    qm=tables((q/'main_table.md').read_text());qs=tables((q/'supplement_tables.md').read_text())
    assert len(oa)==3 and len(ta)==4 and ta==oa+qm
    assert len(ob)==34 and len(tb)==36 and tb==ob[:32]+qs+ob[32:]
    assert len(qs)==2 and len(qs[0].splitlines())==18 and len(qs[1].splitlines())==33
    assert re.findall(r'^Table S(\d+)\.',b,re.M)==[str(i) for i in range(1,36)]
    for num in (32,33):assert f'Table S{num+2}.' in b
    r=refs(a);assert refs(b)==r and set(r)==set(range(1,22))
    assert set(refs(olda).values())<=set(r.values())
    protected=re.compile(r'```.*?```|`[^`\n]+`|\$\$.*?\$\$|\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)',re.S)
    prose=protected.sub('',a.split('# References',1)[0]);order=[]
    for m in re.finditer(r'(?<![\w=])\[((?:\d+(?:[–-]\d+)?)(?:\s*,\s*\d+(?:[–-]\d+)?)*)\](?!\()',prose):
        for part in re.split(r'\s*,\s*',m[1]):
            ends=re.split('[–-]',part)
            for n in range(int(ends[0]),int(ends[-1])+1):
                if 1<=n<=21 and n not in order:order.append(n)
    assert order==list(range(1,22)),order
    theory=(V8/'work/integration_inputs/SUPPLEMENT_QUALIFIED_DRAFT.md').read_text()
    theory='## Arithmetic domain'+theory.split('## Arithmetic domain',1)[1]
    theory=theory.split('## Empirical scope of the qualified ablation',1)[0].strip()
    mapped=manifest['reference_mapping_old_to_current']['20']
    theory=theory.replace('cited to Foong, Bruinsma and Burt (2022)',f'described by Foong, Bruinsma and Burt [{mapped}]')
    theory=re.sub(r'^(#{1,6}) (.+)$',lambda m:m[1]+' '+re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',m[2])).strip(),theory,flags=re.M)
    assert theory in b and 'Foong' in r[mapped]
    for name,assembled in (('manuscript.md',a),('supplement.md',b)):
        source=(V8/name).read_text();parts=protected.findall(source)
        for s,n in collections.Counter(parts).items():assert assembled.count(s)>=n,repr(s)
    assert '0.4217%' in a and 'outcome-free prediction outputs alongside explicitly exposed assessment frames' in b
    result={'status':'PASS_ASSEMBLED_SOURCE_TABLE_AUDIT','main_tables':4,'old_main_tables_unchanged':3,
      'supplement_numbered_tables':35,'supplement_markdown_blocks':36,'old_numbered_tables_unchanged':33,
      'old_unnumbered_markdown_table_unchanged':True,'qualified_context_rows':16,'qualified_t_values':64,
      'qualified_panel_rows':31,'references':21,'old_references_preserved':19,'qualified_reference_number':mapped,
      'math_code_spans_preserved':True,'visual_review_performed':False,'source_hashes':{
      name:sha(V8/name) for name in ('main.complete.md','supplement.complete.md','work/ASSEMBLY.json')}}
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(result)
if __name__=='__main__':main()
