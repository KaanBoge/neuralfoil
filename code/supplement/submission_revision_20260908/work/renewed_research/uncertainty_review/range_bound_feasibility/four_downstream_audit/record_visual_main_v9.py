"""Record the completed human-visible per-page inspection, not an automated visual test."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).parent
R=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v9/work/render_main/v1')
notes=[
'Two-line title, abstract, keywords and introduction start readable; no clipped title or orphan heading.',
'Dense introduction prose remains readable with clean paragraph spacing; footer separate.',
'Introduction continuation and related-work paragraphs complete and legible.',
'Section 2 and provenance subsections readable; source and cohort numbers not clipped.',
'Table 1 whole with caption and all four data rows; input-contract inline subscripts legible.',
'Group/source continuation and applicability inequalities readable; exposure paragraph complete.',
'Equations 1–4, fractions and nested clipping brackets legible; equation numbers aligned.',
'Whole-identity calibration and equations 5–6 readable; rank ceiling glyphs visible.',
'Equations 7–8 and cap-ablation inline expressions fit; no cropped brackets or superscripts.',
'Equation 9 and scale-method text readable; modest bottom whitespace before figure page.',
'Figure 1 all three panels, arrows and caption readable; equation 10 intact and clear of footer.',
'Equation 11, guard exponents and numerical qualification readable; paragraph continuation natural.',
'Equations 12–13 including KL and MAE operators readable; numbered equations and prose separated.',
'Advancement rules and bootstrap prose readable; measurement-sensitivity setup continues naturally.',
'Equations 14–15 readable; section 4 and proof heading have following text.',
'Equations 16–17, maxima and summation limits readable; no math clipping.',
'Adjacent/four-tree bound explanation and percentages readable; no overflow.',
'Table 2 caption and all seven rows stay together; values and status column readable.',
'Figure 2 both panels, legend and caption readable; adverse negative bars visible.',
'Table 3 whole with four rows, arrows and coverage fractions legible; whitespace below is not missing content.',
'Figure 3 both panels and zero-intervention note readable; caption paired; results continuation intact.',
'Table 4 complete with six procedures; long caption wraps cleanly and negative W values remain visible.',
'Qualified/paired results prose and confidence intervals readable; heading has sufficient following text.',
'Four-tree gains and adverse-case text readable; sensitivity heading and following paragraphs fit.',
'Figure 4 both margin plots, legend, axes and caption readable; reproduction heading paired with text.',
'Literal pipeline timings and ULP qualification readable; no clipped numeric ranges.',
'Discussion heading and bound-utility paragraphs readable; next subsection begins with text.',
'Shared-geometry and concentration discussion readable, including zero-loss formula.',
'Limitations section readable; paragraph transitions and numerical caveats intact.',
'Limitations and conclusions readable; continuation to page 31 natural.',
'Conclusion ending, availability, AI disclosure and references 1–4 readable; no split reference item.',
'References 5–17 readable with hanging indents and wrapped URLs; all entries stay intact.',
'References 18–23 readable; final entry and URL complete; final-page whitespace acceptable.'
]
assert len(notes)==33
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pdf=R/'NeuralFoil_Measurement_Correction_Manuscript.pdf'
pages=[]
for n,note in enumerate(notes,1):
    p=R/f'page-{n}.png'
    pages.append({'page':n,'png_sha256':sha(p),'result':'PASS','individually_viewed_original_resolution':True,'reviewer':'/root/astra_cycle2_review','checks':note})
out={'schema':'INDIVIDUAL_PAGE_VISUAL_LEDGER_V1','pdf_sha256':sha(pdf),'pdf_path':str(pdf),'docx_sha256':sha(R/'NeuralFoil_Measurement_Correction_Manuscript.docx'),'main_source_sha256':sha(R/'main.complete.md'),'reviewer':'/root/astra_cycle2_review','pages':pages,'necessary_defects':[], 'inspection_method':'All 33 individual PNGs displayed with explicit original detail at 1547x2002; first 1–3 initially resized by output transport, then all three reopened at original detail. No contact sheet used.','supplementary_check':'PDF page 11 final body character bottom 704.0788 pt; footer begins 749.17 pt; no collision.','diagnostics':['Initial optional coordinate check used a runtime without pdfplumber and failed import; repeated with bundled runtime. No source/render changed.']}
with (HERE/'VISUAL_MAIN_V9_V1_PAGE_LEDGER.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(sha(HERE/'VISUAL_MAIN_V9_V1_PAGE_LEDGER.json'))
