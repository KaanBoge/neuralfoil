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
       ["Approximate totals", "over 400,000", "about 3.4 million", ""],
       ["XFOIL 6.99 viscous simulations", "about 11,000", "not applicable", "Teacher decomposition and head-to-head"]]
story.append(mk_table(inv, [AV * 0.34, AV * 0.14, AV * 0.18, AV * 0.34]))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Measurements used as truth: 41,683 wind-tunnel points in the low-speed corpus (10,608 clean drag, "
    "31,075 lift; 148 airfoil entries; UIUC Low-Speed Airfoil Tests volumes 1 to 3 and SoarTech 8, "
    "GPL-licensed ASCII, therefore free of digitization error), plus the primary transonic set of 92 "
    "digitized points (Harris TM-81927, Ferri WR L-143) and the TN 3607 calibration and TN 1546 holdout "
    "extractions (242 and 133 drag points, 60 and 60 lift points).", S["body"]))

story.append(Paragraph("Appendix B. Final head-to-head, verbatim run output", S["h1"]))
try:
    txt = open(os.path.join(SITE, "lsat-headtohead2.txt"), encoding="utf-8", errors="replace").read()
except OSError:
    txt = open(os.path.join(BASE, "..", "lsat", "lsat-headtohead2.txt"), encoding="utf-8", errors="replace").read()
for line in txt.rstrip().split("\n"):
    story.append(Paragraph(line.replace(" ", "&nbsp;") if line.startswith(" ") else inline(line), S["mono"]))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Corrections are out of fold: each airfoil is scored by a model trained without it. XFOIL is scored "
    "only on the points where it converged, which is its best case.", S["caption"]))

story.append(Paragraph("Appendix C. Measured error map by Reynolds number", S["h1"]))
emap = [["Reynolds band", "Points", "Median error, counts", "p90, counts", "Mean error, counts"],
        ["under 45,000", "23", "101.6", "512.0", "194.2"],
        ["45,000 to 75,000", "1,590", "39.6", "147.1", "70.3"],
        ["75,000 to 150,000", "2,761", "20.9", "98.0", "46.7"],
        ["150,000 to 250,000", "3,182", "12.1", "74.3", "32.3"],
        ["250,000 to 350,000", "2,491", "9.8", "78.1", "31.1"],
        ["350,000 to 600,000", "561", "9.4", "99.1", "31.7"]]
story.append(mk_table(emap, [AV * 0.26, AV * 0.14, AV * 0.22, AV * 0.18, AV * 0.20]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Mean-of-8 core before corrections. Above Re 150,000 the median error is comparable to the "
    "measurement's own spanwise drag variation (median half-spread 10 counts).", S["caption"]))

story.append(Paragraph("Appendix D. Ensemble disagreement as an error predictor", S["h1"]))
sp = [["Disagreement decile, counts", "Median true error, counts", "Points"],
      ["1.0 to 4.6", "8.1", "1,061"], ["4.6 to 6.0", "9.0", "1,061"],
      ["6.0 to 7.6", "8.6", "1,061"], ["7.6 to 9.3", "9.4", "1,061"],
      ["9.3 to 11.3", "11.4", "1,062"], ["11.3 to 14.5", "15.5", "1,061"],
      ["14.5 to 18.3", "22.9", "1,060"], ["18.3 to 25.3", "24.7", "1,061"],
      ["25.3 to 47.2", "40.5", "1,062"], ["47.2 to 608.4", "108.5", "1,062"]]
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
       ["Drag correction v3", "9-feature boosted trees, tighter regularization", "+12.4 percent, both transfers improve", "Shipped"],
       ["Lift correction v2", "16-feature boosted trees", "+26.7 percent, both transfers improve", "Shipped"]]
story.append(mk_table(att, [AV * 0.24, AV * 0.24, AV * 0.32, AV * 0.20]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "The ship rule was declared before each fit: improvement on airfoil-disjoint folds AND in both "
    "cross-facility transfer directions. Eight attempts, two survivors and one superseded predecessor. "
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
         ["correction-cd3.json, correction-cl2.json", "Shipped correction models with reference vectors"],
         ["oof2.csv, oof3.csv", "Out-of-fold correction predictions used for scoring"],
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
