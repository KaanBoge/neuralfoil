"""Record direct human-style image review and independently authenticate text successor."""
from pathlib import Path
import hashlib, json, struct

P = Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
V = P/'submission_revision_20260908/renewed_manuscript_v9'
O = Path(__file__).parent
pins = {}
def read(p, expected=None):
    b = p.read_bytes(); h = hashlib.sha256(b).hexdigest()
    if expected is not None: assert h == expected, str(p)
    pins[str(p)] = h
    return b
def save(name, obj):
    with (O/name).open('x') as f: json.dump(obj, f, indent=2); f.write('\n')

c = json.loads(read(V/'work/ROOT_ASSEMBLY_CONFIG_v2.json', '9c465fda5c7933381c8902bcd0e0cefb9952e4d23fbe08d9fe16a21ed3f808b9'))
a = json.loads(read(V/'work/ASSEMBLY.json', '2b5368e3cf0379117faf31dbaa05cf97aecc6d3726291f896d583719bd729375'))
assert len(c['inputs']) == 32
for entry in c['inputs'].values(): read(P/entry['path'], entry['sha256'])
assert a['inputs'] == {x['path']: x['sha256'] for x in c['inputs'].values()}
assert a['predecessor'] == c['predecessor']
read(V/'assemble_submission.py', a['assembler_sha256'])
v1 = V/'work/assembly_versions/v1'; v2 = V/'work/assembly_versions/v2'
for name, h in c['predecessor']['sha256'].items(): read(v1/name, h)
for name, h in a['outputs'].items():
    read(V/name,h); read(v2/name,h)
read(v2/'ASSEMBLY.json', pins[str(V/'work/ASSEMBLY.json')])
read(v2/'CONFIG.json', pins[str(V/'work/ROOT_ASSEMBLY_CONFIG_v2.json')])
old = read(v1/'supplement.complete.md')
new = read(v2/'supplement.complete.md')
before = b'Accuracy and reliability of measurement informed NeuralFoil drag correction'
after = 'Accuracy–harm trade-offs in measurement-informed NeuralFoil drag correction'.encode()
assert old.count(before) == 1 and old.replace(before,after,1) == new
assert read(v1/'main.complete.md') == read(v2/'main.complete.md')
main_pages = []
for n in range(1,34):
    p1 = V/f'work/render_main/v1/page-{n}.png'; p2 = V/f'work/render_main/v2/page-{n}.png'
    assert read(p1) == read(p2)
    main_pages.append({'page':n,'png_sha256':pins[str(p2)],'byte_identical_to_reviewed_v1':True})
assembly_pins = dict(pins)
save('V9_ASSEMBLY_V2_QA.json', {'result':'PASS','reviewer':'astra_cycle2_review', 'scope':'32 selected inputs, preserved predecessor, title-only text successor; no scientific recalculation', 'pins':assembly_pins, 'main_unchanged':True,'supplement_only_change':{'before':before.decode(),'after':after.decode()},'all_other_text_tables_captions_references_unchanged':True,'main_raster_identity':main_pages})

observations = [
 'Corrected accompaniment title, reader guide and populated contents fit clearly.',
 'S1 recovery and cohort discussion; both hashes fit; identity heading retained with text.',
 'Identity-purge continuation and external cohorts; section-end whitespace acceptable.',
 'S2 Table S1 feature inventory and X44 continuation; complete table/caption.',
 'Training balance S1 equation; expert Table S2 begins with first five rows.',
 'Table S2 repeated header and experts 6–27; features paragraph continues normally.',
 'Feature construction and family specifications; dense but readable.',
 'Spline/simplex/capacity/kernel specifications; enclosing comparison heading with body.',
 'Enclosing comparison continuation and inference-order text; clean section end.',
 'S3 policies, equations S2–S4 and geometry heading; native symbols clear.',
 'Geometry equation S5 and preserved numerical-failure explanation; clean continuation.',
 'Neural specification and complete Table S3, all ten procedures readable.',
 'Neural warning continuation and oracle equation S6; scope paragraphs intact.',
 'S4 calibration split, rank and family counts; normal paragraph continuation.',
 'Adaptive-scale method, inference/fallback and metric definitions; clean typography.',
 'Decision and bootstrap scope; section-end whitespace, no orphan heading.',
 'S5 scope and projection S7; proof starts and continues without lost symbols.',
 'Projection proof and calibration floor equations S8–S12; fractions/rank readable.',
 'Projection consequence S13 and inactive-cap S14–S15; sums intact above footer.',
 'Inactive cap S16–S17 and reproducibility paths; code strings fit.',
 'Exact certificate commands and sensitivity S18; code lines and sums readable.',
 'Deletion definitions and complete Table S4; dense result text remains above footer.',
 'Statistical boundaries and qualified numerical domain; exponents/gates clear.',
 'Qualified arithmetic S19–S21 and rounding allowance; equations correctly separated.',
 'Rounding bounds S22–S25; inequalities, fractions and symbols intact.',
 'KL S26–S27 and confidence discussion; root/rank symbols readable.',
 'Conservative root interpretation and inward interpolation S28–S29; clean layout.',
 'Adjacent-pair D/R method and feasibility discussion; normal continuation.',
 'Final paired certificate and retained failed resource gate; all-context heading with body.',
 'All-context paired results and four-tree matching S30–S31; interval symbols clear.',
 'Four-addition allowance S32–S33 and nonloosening proof; no equation clipping.',
 'Four-tree final and all-context exact results; long numeric strings readable.',
 'All-context qualification continuation; clean end of S5 with whitespace.',
 'S6 connected feature/correction reproduction; count and exponent typography clear.',
 'Feature bridge and headline-reference reconstruction; normal paragraph continuation.',
 'Runtime versions and independently provisioned environment; dense body readable.',
 'Environment differences, retained failure and portable-certificate introduction.',
 'Portable exact and qualified confidence replay; endpoint difference counts readable.',
 'Reconciliation, private-package limits and timing heading retained with body.',
 'Timing-scope continuation and S13 cross-reference; clean section end.',
 'S7 complete-panel guide; units and tolerance explanation readable.',
 'Figure S1 both heatmap panels, all configurations, legend and full caption fit.',
 'Table S5 capped full; all 31 view rows and six columns on one page.',
 'Table S6 capped half; all 31 view rows and six columns on one page.',
 'Table S7 upper free full; all 31 view rows and six columns on one page.',
 'Table S8 upper free half; all 31 view rows and six columns on one page.',
 'Table S9 positive log full; all 31 view rows, including adverse values, on one page.',
 'Table S10 positive log half; all 31 view rows and six columns on one page.',
 'Table S11 proper capped full; all 31 view rows and six columns on one page.',
 'Table S12 proper capped half; all 31 view rows and six columns on one page.'
]
assert len(observations) == 50
render = V/'work/render_supplement/v2'
pdf = render/'NeuralFoil_Measurement_Correction_Supplement.pdf'
read(pdf,'3da70f48fe206d2bc8b304afa1006b32d0e57b76c099307ce3e945848b456d56')
pages = []
for n, note in enumerate(observations,1):
    p = render/f'page-{n}.png'; raw = read(p)
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    shape = struct.unpack('>II',raw[16:24]); assert shape == (1547,2002)
    pages.append({'page':n,'path':str(p),'png_sha256':pins[str(p)],'result':'PASS','individually_viewed_original_resolution':True,'dimensions':list(shape),'reviewer':'astra_cycle2_review','observed_content':note,'checks':['readability','glyphs and mathematics','clipping and overflow','caption/table continuity','page breaks and footer separation'],'defects':[]})
save('VISUAL_SUPPLEMENT_V9_V2_1_50_PAGE_LEDGER.json',{'pdf':str(pdf),'pdf_sha256':pins[str(pdf)],'reviewer':'astra_cycle2_review','pages':pages,'scope':'Only pages 1–50 directly inspected individually using original-resolution image output; no claim for 51–101.','transport_note':'An earlier five-page batch for pages 6–10 was truncated and not counted. Each was subsequently opened in smaller complete batches.','result':'PASS'})
with (O/'VISUAL_SUPPLEMENT_V9_V2_1_50_REVIEW.md').open('x') as f:
    f.write('# Supplement V9 v2 visual review: pages 1–50\n\nPASS. All 50 assigned pages were individually inspected at original 1547×2002 resolution; no necessary layout fix was found. No claim is made for pages 51–101, which belong to the root reviewer.\n\nThe corrected title and populated contents are readable. Native proof equations S1–S33 have no observed missing glyphs or clipping. Table S2 continues with a repeated header; Tables S3/S4 and all eight 31-row matrices S5–S12 are complete on their respective pages. Figure S1 retains both panels, numeric signs, legend and caption. Dense body pages remain separate from the footer; shorter section-ending pages are acceptable, not omissions.\n\nThe exact PDF and individual PNG hashes and page-specific observations are in VISUAL_SUPPLEMENT_V9_V2_1_50_PAGE_LEDGER.json. This was a visual/layout review, not another numerical reassessment, render or publication approval.\n')
with (O/'V9_ASSEMBLY_V2_REVIEW.md').open('x') as f:
    f.write('# Assembly V9 v2 preserved-successor review\n\nPASS. Reauthenticated all 32 selected input pins, config, assembler, current outputs, preserved v1 predecessor and v2 snapshots. The main Markdown is byte-identical. The entire supplement is identical except the single accompanying-manuscript title replacement: “Accuracy and reliability of measurement informed NeuralFoil drag correction” → “Accuracy–harm trade-offs in measurement-informed NeuralFoil drag correction”. Thus every table, caption, equation, scientific paragraph and reference outside that title is unchanged from the independently audited v1.\n\nAll 33 main v2 page images are independently byte-compared equal to the directly reviewed v1 pages. Supplement visual review is separately limited to pages 1–50. V1 reports were not overwritten. See V9_ASSEMBLY_V2_QA.json for exact pins. No scientific data, inference, resampling, models or rendering was executed.\n')
for p, h in pins.items(): assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h
print(json.dumps({'status':'PASS','assembly_inputs':32,'main_identical_pages':33,'supplement_pages_directly_viewed':50,'outputs':[x for x in ['V9_ASSEMBLY_V2_QA.json','V9_ASSEMBLY_V2_REVIEW.md','VISUAL_SUPPLEMENT_V9_V2_1_50_PAGE_LEDGER.json','VISUAL_SUPPLEMENT_V9_V2_1_50_REVIEW.md']]}))
