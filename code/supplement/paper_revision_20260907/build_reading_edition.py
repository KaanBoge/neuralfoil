"""Pandoc native-math DOCX + restrained typography, using preserved design helpers."""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import subprocess
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior_design', HERE.parent/'modern_edition/build_document.py')
design = importlib.util.module_from_spec(spec)
spec.loader.exec_module(design)
OLD_WIDTHS = design.table_widths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['main','supplement'])
    ap.add_argument('--page-map',type=Path)
    args = ap.parse_args()
    mainpaper = args.kind == 'main'
    name = 'NeuralFoil_Measurement_Informed_Drag_Correction' if mainpaper else 'NeuralFoil_Measurement_Audit_Supplement'
    source = HERE/('manuscript.md' if mainpaper else 'supplement.complete.md')
    text = source.read_text()
    if not mainpaper:
        # One editable internal navigation block for the complete supplement.
        text = text.replace('# Supplementary revision notice', '## Contents\n\nNAVIGATION_PLACEHOLDER\n\n# Supplementary revision notice',1)
        text = text.replace('title: "Supplement: Historical NeuralFoil Measurement Audit and Recovered-Input Corrigendum"',
                            'title: "Historical NeuralFoil Measurement Audit and Recovered Input Supplement"')
    else:
        # Descriptive section headings keep the visual hierarchy without punctuation.
        text = re.sub(r'^(#{2,3}) (?:\d+\.\d+|A\.\d+|B\.\d+)\s+',r'\1 ',text,flags=re.M)
    # New editorial headings use plain words. Preserve the dated historical body's text.
    limit=text.find('# Historical September 6 measurement audit') if not mainpaper else len(text)
    prefix=text[:limit]
    prefix=re.sub(r'^(#{1,3}) (.+)$',lambda m:m.group(1)+' '+re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',m.group(2))).strip(),prefix,flags=re.M)
    text=prefix+text[limit:]
    work=HERE/'work'/args.kind;work.mkdir(parents=True,exist_ok=True)
    normalized=work/'render_source.md';normalized.write_text(text)
    raw=work/'raw.docx'
    subprocess.run(['/opt/anaconda3/bin/pandoc',str(normalized),
        '--from','markdown+tex_math_dollars+pipe_tables+grid_tables+autolink_bare_uris',
        '--to','docx','--resource-path',str(HERE),'--output',str(raw)],check=True,cwd=HERE)
    document=Document(raw)
    if mainpaper:
        widths = {'1':[2.65,.82,.82,1.12,1.29], '2':[1.85,1.1,1.75,2.0],
            '3':[2.1,1.35,1.63,1.62], '4':[2.0,.85,.95,1.0,1.9],
            '5':[2.0,1.55,1.55,1.6], '6':[1.6,1.275,1.275,1.275,1.275],
            '7':[1.9,2.45,2.35], 'A1':[.65,6.05], 'A2':[.55,2.5,3.65],
            'B1':[1.45,2.6,2.65]}
        def table_widths(t,c):
            w=widths.get(c,[1.25,5.45] if len(t.columns)==2 else [6.7/len(t.columns)]*len(t.columns))
            assert len(w)==len(t.columns),(c,len(w),len(t.columns))
            assert abs(sum(w)-6.7)<1e-5
            return w
    else:
        def table_widths(t,c):
            head=[x.text.strip() for x in t.rows[0].cells]
            if head[0]=='View': return [1.95,.45,.72,.92,.92,.79,.95]
            if head[0]=='Procedure': return [1.9,.95,1.0,.8,2.05]
            if head[0]=='Cohort construction': return [2.15,.8,.8,.9,1.0,1.05]
            if head[0]=='Stage': return [1.35,2.55,2.8]
            return OLD_WIDTHS(t,c)
    design.table_widths=table_widths
    design.TITLE='Measurement informed drag correction for NeuralFoil across airfoil groups and experimental sources' if mainpaper else 'Historical NeuralFoil Measurement Audit and Recovered Input Supplement'
    pages=json.loads(args.page_map.read_text()) if args.page_map else {}
    headings=design.format_document(document,pages)
    # New long tables may continue cleanly with repeated headers, not a whole-table keep chain.
    for t in document.tables:
        if mainpaper or len(t.rows)>20:
            for i,row in enumerate(t.rows):
                for cell in row.cells:
                    for p in cell.paragraphs:
                        p.paragraph_format.keep_with_next=(i==0)
                        if len(t.columns)>=7:
                            for r in p.runs:
                                design.font(r,design.SANS,8.8)
        if mainpaper and t.rows[0].cells[0].text.strip() in {'Index','Index (one based)'}:
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for r in p.runs: design.font(r,design.SANS,9.2)
    # Keep first-page abstract together only when it fits naturally; no ornamental box.
    for p in document.paragraphs:
        txt=p.text.strip()
        if p.style.name=='Title':
            for r in p.runs: design.font(r,design.SANS,25,'000000',True)
        if p._p.xpath('.//m:oMathPara'):
            p.paragraph_format.keep_together=True
            p.paragraph_format.space_before=Pt(7)
            p.paragraph_format.space_after=Pt(9)
        if not mainpaper and p.style.name.startswith('Heading') and txt.startswith(('Appendix S','Appendix T','Historical September 6')):
            p.paragraph_format.page_break_before=True
        if mainpaper and txt=='Observation level harms and conditional uncertainty':
            p.paragraph_format.page_break_before=True
        if mainpaper and txt.startswith('The moderate full-strength control has'):
            p.paragraph_format.keep_together=True
        if mainpaper and re.match(r'^\[\d+\]',txt):
            p.paragraph_format.space_after=Pt(3)
        if p.style.name.startswith('Heading'):
            p.paragraph_format.keep_with_next=True
    header=document.sections[0].header.paragraphs[0]
    header.clear()
    design.font(header.add_run('NEURALFOIL MEASUREMENT INFORMED DRAG CORRECTION' if mainpaper else 'NEURALFOIL MEASUREMENT AUDIT SUPPLEMENT'),design.SANS,8.2,'000000')
    document.core_properties.subject='Adaptive drag correction with measurement provenance and source transfer' if mainpaper else 'Preserved historical measurement audit and complete correction assessment'
    output=HERE/'deliverables'/(name+'.docx');output.parent.mkdir(exist_ok=True)
    document.save(output)
    (work/'headings.json').write_text(json.dumps(headings,indent=2)+'\n')
    print(output)

if __name__=='__main__': main()
