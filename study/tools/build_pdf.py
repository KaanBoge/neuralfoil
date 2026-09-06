"""Build the complete research-record PDF from the answer document plus
front matter and data appendices. Markdown subset: headings, bold, tables,
bullets, paragraphs. No unicode sub/superscripts (reportlab core fonts)."""
import csv, os, re
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, PageBreak, KeepTogether)

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = r"/mnt/c/Users/kaanb/nf-site-work/neuralfoil/study/data"
OUT = os.path.join(BASE, "NeuralFoil-Study-Complete-Record.pdf")

INK = colors.HexColor("#14202b")
MUTED = colors.HexColor("#5b6b7a")
ACC = colors.HexColor("#1f5fa9")
RULE = colors.HexColor("#c8d3dd")
BG = colors.HexColor("#eef3f8")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold",
                            fontSize=21, leading=25, textColor=INK, spaceAfter=6),
    "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=11.5, leading=15.5, textColor=MUTED, spaceAfter=14),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=14.5, leading=18, textColor=ACC, spaceBefore=16, spaceAfter=7),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=11.5, leading=14.5, textColor=INK, spaceBefore=11, spaceAfter=5),
    "body": ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=9.6, leading=13.6, textColor=INK, alignment=TA_JUSTIFY,
                           spaceAfter=7),
    "bullet": ParagraphStyle("bullet", parent=ss["Normal"], fontName="Helvetica",
                             fontSize=9.6, leading=13.4, textColor=INK, leftIndent=13,
                             bulletIndent=3, spaceAfter=3.5),
    "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=8.2, leading=10.6, textColor=INK),
    "cellh": ParagraphStyle("cellh", parent=ss["Normal"], fontName="Helvetica-Bold",
                            fontSize=8.2, leading=10.6, textColor=colors.white),
    "mono": ParagraphStyle("mono", parent=ss["Normal"], fontName="Courier",
                           fontSize=7.7, leading=9.6, textColor=INK),
    "caption": ParagraphStyle("caption", parent=ss["Normal"], fontName="Helvetica-Oblique",
                              fontSize=8.4, leading=11, textColor=MUTED, spaceAfter=9),
}

def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<font face='Courier' size='8.6'>\1</font>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r"<b>\1</b>", t)
    return t

def mk_table(rows, widths=None):
    head = [Paragraph(inline(c), S["cellh"]) for c in rows[0]]
    body = [[Paragraph(inline(c), S["cell"]) for c in r] for r in rows[1:]]
    t = Table([head] + body, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACC),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t

def md_to_flow(md, avail):
    flow, tbl = [], []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            tbl.append(cells)
            continue
        if tbl:
            ncol = max(len(r) for r in tbl)
            tbl = [r + [""] * (ncol - len(r)) for r in tbl]
            w = [avail * 0.30] + [(avail * 0.70) / (ncol - 1)] * (ncol - 1) if ncol > 1 else [avail]
            flow.append(mk_table(tbl, w)); flow.append(Spacer(1, 9)); tbl = []
        if not line.strip():
            continue
        if line.startswith("### "):
            flow.append(Paragraph(inline(line[4:]), S["h2"]))
        elif line.startswith("## "):
            flow.append(Paragraph(inline(line[3:]), S["h1"]))
        elif line.startswith("# "):
            flow.append(Paragraph(inline(line[2:]), S["title"]))
        elif line.startswith("- ") or line.startswith("* "):
            flow.append(Paragraph(inline(line[2:]), S["bullet"], bulletText="•"))
        elif line.startswith("_") and line.endswith("_") and len(line) > 2:
            flow.append(Paragraph(inline(line[1:-1]), S["caption"]))
        else:
            flow.append(Paragraph(inline(line), S["body"]))
    if tbl:
        ncol = max(len(r) for r in tbl)
        tbl = [r + [""] * (ncol - len(r)) for r in tbl]
        w = [avail * 0.30] + [(avail * 0.70) / (ncol - 1)] * (ncol - 1) if ncol > 1 else [avail]
        flow.append(mk_table(tbl, w))
    return flow

TITLE = "From Black Box to Bounded Tool: NeuralFoil Audit and Measured-Correction Release"

def decorate(canv, doc):
    canv.saveState()
    canv.setFont("Helvetica", 7.4)
    canv.setFillColor(MUTED)
    canv.drawString(0.9 * inch, 0.62 * inch, "Boge, 2026. Complete research record.")
    canv.drawRightString(LETTER[0] - 0.9 * inch, 0.62 * inch, "Page %d" % canv.getPageNumber())
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.4)
    canv.line(0.9 * inch, 0.78 * inch, LETTER[0] - 0.9 * inch, 0.78 * inch)
    if canv.getPageNumber() > 1:
        canv.line(0.9 * inch, LETTER[1] - 0.72 * inch, LETTER[0] - 0.9 * inch, LETTER[1] - 0.72 * inch)
        canv.drawString(0.9 * inch, LETTER[1] - 0.62 * inch, TITLE)
    canv.restoreState()

doc = BaseDocTemplate(OUT, pagesize=LETTER, title=TITLE, author="Kaan Boge",
                      subject="Validation and correction of the NeuralFoil surrogate",
                      leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                      topMargin=0.95 * inch, bottomMargin=0.9 * inch)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="n")
doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=decorate)])
AV = doc.width

story = []
story += md_to_flow(open(os.path.join(BASE, "pdf-front.md"), encoding="utf-8").read(), AV)

ans = open(os.path.join(BASE, "research-answer.md"), encoding="utf-8").read()
story += md_to_flow(ans, AV)

# ---------------- appendices -----------------
story.append(PageBreak())
story.append(Paragraph("Appendix A. Simulation and measurement inventory", S["h1"]))
story.append(Paragraph(
    "Every computational and experimental element of the study, counted. Network evaluations are "
    "individual forward passes of a NeuralFoil model at one condition; a condition run through all "
    "eight shipped model sizes counts as eight.", S["body"]))
inv = [["Element", "Conditions", "Network evaluations", "Purpose"],
       ["Failure-map atlas (1,655 UIUC airfoils, 8 sizes)", "312,795", "2,502,360", "Operating-envelope map, confidence blindspot discovery"],
       ["Drag corpus, base capture (148 airfoils)", "13,394", "107,152", "Core selection, measured error map, correction training"],
       ["Drag corpus, extended capture (transition, moment)", "13,394", "107,152", "Correction v2 and v3 feature set"],
       ["Lift corpus (108 airfoils, 474 sweeps)", "31,075", "248,600", "Lift validation, lift correction training"],
       ["Stall fine grids (471 sweeps, 0.25 deg)", "47,571", "380,568", "CLmax and stall-angle scoring"],
       ["n_crit sensitivity resample (3 conventions)", "5,241", "41,928", "Convention robustness"],
       ["Probe batteries (hard-wrongs, smoothness, geometry, moment)", "about 6,000", "about 20,000", "Failure-mode sweep, noise floor"],
       ["Transonic phase batteries and fits", "about 4,000", "about 12,000", "Onset, magnitude, recalibration attempts"],
       ["Double-clean re-analysis (2026-09-06; no new network runs, recomputed from stored predictions)", "8,634", "0", "Corrected error maps, correction retraining and head-to-head after the export audit"],
       ["Approximate totals", "over 400,000", "about 3.4 million", ""],
       ["XFOIL 6.99 viscous simulations", "about 11,000", "not applicable", "Teacher decomposition and head-to-head"]]
story.append(mk_table(inv, [AV * 0.34, AV * 0.14, AV * 0.18, AV * 0.34]))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Measurements used as truth: the low-speed corpus (8,634 double-clean drag points over 135 airfoils after "
    "the part 14 correction, superseding the 10,608 name-clean points of parts 10 to 13; 31,075 lift points over "
    "108 airfoils; UIUC Low-Speed Airfoil Tests volumes 1 to 3 and SoarTech 8, "
    "GPL-licensed ASCII, therefore free of digitization error), plus the primary transonic set of 92 "
    "digitized points (Harris TM-81927, Ferri WR L-143) and the TN 3607 calibration and TN 1546 holdout "
    "extractions (242 and 133 drag points, 60 and 60 lift points).", S["body"]))

story.append(Paragraph("Appendix B. Double-clean re-analysis, verbatim run output (part 14)", S["h1"]))
try:
    txt = open(os.path.join(SITE, "dc-report.txt"), encoding="utf-8", errors="replace").read()
except OSError:
    txt = open(os.path.join(BASE, "..", "lsat", "dc-report.txt"), encoding="utf-8", errors="replace").read()
for line in txt.rstrip().split("\n"):
    story.append(Paragraph(line.replace(" ", "&nbsp;") if line.startswith(" ") else inline(line), S["mono"]))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "The drag correction shown as 'new NF + corrections' in this output FAILED its ship rule on the "
    "double-clean corpus (the [CD] SHIP: False line) and is not shipped; the shipped drag prediction is the "
    "mean-of-8 line. Corrections are out of fold: each airfoil is scored by a model trained without it. "
    "XFOIL is scored only on the points where it converged, which is its best case.", S["caption"]))

story.append(Paragraph("Appendix C. Measured error map by Reynolds number (double-clean corpus)", S["h1"]))
emap = [["Reynolds band", "Points", "Median error, counts", "p90, counts", "Mean error, counts"],
        ["under 45,000", "23", "101.6", "512.0", "194.2"],
        ["45,000 to 75,000", "1,323", "39.5", "143.4", "67.8"],
        ["75,000 to 150,000", "2,267", "19.3", "88.0", "43.6"],
        ["150,000 to 250,000", "2,697", "10.9", "62.1", "28.7"],
        ["250,000 to 350,000", "1,844", "8.1", "47.1", "23.1"],
        ["350,000 to 600,000", "480", "7.3", "39.1", "19.8"]]
story.append(mk_table(emap, [AV * 0.26, AV * 0.14, AV * 0.22, AV * 0.18, AV * 0.20]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Mean-of-8 core, no correction, on the 8,634 double-clean points. Above Re 150,000 the median error is "
    "at or below the measurement's own spanwise drag variation (median half-spread 10.5 counts).", S["caption"]))

story.append(Paragraph("Appendix D. Ensemble disagreement as an error predictor (double-clean corpus)", S["h1"]))
sp = [["Disagreement decile, counts", "Median true error, counts", "Points"],
      ["1.0 to 4.5", "7.3", "864"], ["4.5 to 6.1", "8.0", "863"],
      ["6.1 to 7.7", "7.8", "863"], ["7.7 to 9.4", "8.1", "864"],
      ["9.4 to 11.5", "10.7", "863"], ["11.5 to 14.6", "14.3", "863"],
      ["14.6 to 18.5", "21.8", "864"], ["18.5 to 25.3", "23.8", "863"],
      ["25.3 to 47.2", "38.0", "864"], ["47.2 to 608.4", "96.9", "865"]]
story.append(mk_table(sp, [AV * 0.36, AV * 0.34, AV * 0.30]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Monotonic across all ten deciles, which is what licenses shipping the disagreement band as an "
    "error indicator. This measured curve is the expected-error lookup in the released tool.", S["caption"]))

story.append(Paragraph("Appendix E. Correction attempt history and ship decisions", S["h1"]))
att = [["Attempt", "Form", "Held-out result", "Decision"],
       ["Transonic F1 to F3, null", "power laws in (M - M_crit)", "Harris 78 percent worse; TN 1546 only 9.3 percent better", "Rejected by pre-registered one-shot"],
       ["Transonic similarity S1, S2", "thickness-scaled similarity", "86.0 vs 89.7 counts cross-validated; S2 overfits", "Rejected, exploratory"],
       ["Lift-break onset shift", "one parameter", "+2 percent, worsens TN 1546", "Rejected"],
       ["Lift-break alpha-detached onset", "one parameter", "-2 percent", "Rejected"],
       ["Drag correction v1", "21-term ridge", "+10.5 percent, both transfers improve", "Shipped, later superseded"],
       ["Drag correction v2", "16-feature boosted trees", "+15.7 percent but one facility transfer worsens", "Rejected"],
       ["Drag correction v3 (name-clean corpus)", "9-feature boosted trees, tighter regularization", "+12.4 percent, both transfers improve", "Shipped 2026-08-30"],
       ["Lift correction v2 (name-clean corpus)", "16-feature boosted trees", "+26.7 percent, both transfers improve", "Shipped 2026-08-30"],
       ["Drag correction v3 (double-clean corpus)", "same form, same rule", "+15.4 percent on folds, but volumes transfer worsens 34.8 to 35.9", "Rejected; the 2026-08-30 drag correction WITHDRAWN 2026-09-06"],
       ["Lift correction v2 (double-clean corpus)", "same form, same rule", "+35.4 percent, both transfers improve", "Shipped 2026-09-06, replacing the name-clean version"]]
story.append(mk_table(att, [AV * 0.24, AV * 0.24, AV * 0.32, AV * 0.20]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "The ship rule was declared before each fit: improvement on airfoil-disjoint folds AND in both "
    "cross-facility transfer directions. Ten attempts; the shipped state at the end is one lift correction. "
    "The name-clean corpus of the 2026-08-30 attempts contained 1,974 tripped runs (18.6 percent) let through by "
    "a name-only configuration filter; the double-clean rows repeat the attempts on honest data. "
    "The rejections are as much a result as the ships.", S["caption"]))

story.append(Paragraph("Appendix F. Reproducibility", S["h1"]))
story.append(Paragraph(
    "Environment: NeuralFoil 0.3.3, AeroSandbox 4.2.10, numpy 2.5.2, scipy, scikit-learn 1.9.0, "
    "Python 3.14.4, pinned in a dedicated virtual environment; XFOIL 6.99 built headless from source. "
    "The browser port of the network and of both correction models is verified against the Python path "
    "on every page load (40 reference runs to about 1e-15; tree ensembles to 0.0 exactly).", S["body"]))
files = [["Artifact", "Contents"],
         ["lsat-corpus.csv", "Parsed measured corpus, 14,773 points with source and configuration"],
         ["lsat-nf.csv, lsat-nf2.csv", "All eight model sizes at every measured condition, base and extended captures"],
         ["lsat-xfoil.csv", "Every XFOIL run, 7,897 converged points"],
         ["lsat-report.txt, lsat-lift-report.txt", "Error maps for drag and lift, worst and best airfoils"],
         ["lsat-headtohead2.txt", "Final four-way comparison output"],
         ["dc-correction-cl2.json", "The shipped lift correction (double-clean), with reference vectors"],
         ["correction-cd3.json, correction-cl2.json", "The withdrawn 2026-08-30 corrections, kept for the record"],
         ["dc-report.txt, dc-oof.csv, dc-by-airfoil.csv, lsat_doubleclean.py", "The part 14 re-analysis and its out-of-fold predictions"],
         ["oof2.csv, oof3.csv", "Out-of-fold predictions of the withdrawn 2026-08-30 corrections"],
         ["export-manifest, export-missing-files, export-unused-data (2026-09-06)", "The audited export records that found the contamination"],
         ["master-dataset.csv", "The 92-point primary transonic dataset with provenance and uncertainty"],
         ["research-answer.md", "This document's parts 1 to 13 in source form"],
         ["lsat_*.py, atlas*.py, fit_definitive.py, probes.py", "Every pipeline script, in execution order"]]
story.append(mk_table(files, [AV * 0.34, AV * 0.66]))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "All artifacts are published under study/ at kaanboge.github.io/neuralfoil. Data files carry the "
    "licenses of their sources: the UIUC corpus is GPL v2 (Selig et al.), the NACA and NASA reports are "
    "public domain, and NeuralFoil is MIT (Sharpe).", S["body"]))

doc.build(story)
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
