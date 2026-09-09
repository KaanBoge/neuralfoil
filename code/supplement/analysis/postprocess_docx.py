from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph


ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "output" / "docx" / "NeuralFoil_Journal_Manuscript_Final.docx"

NAVY = "000000"
BLUE = "000000"
MID_GRAY = "667085"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, start=90, bottom=70, end=90) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:cantSplit")
    tr_pr.append(node)


def set_cell_border(cell, edge: str, *, value: str, size: int, color: str = "000000") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    node = borders.find(qn(f"w:{edge}"))
    if node is None:
        node = OxmlElement(f"w:{edge}")
        borders.append(node)
    node.set(qn("w:val"), value)
    node.set(qn("w:sz"), str(size))
    node.set(qn("w:color"), color)


def set_aiaa_table_borders(table) -> None:
    """Apply AIAA's horizontal-rule table convention without vertical rules."""
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    settings = {
        "top": ("double", "6"),
        "bottom": ("double", "6"),
        "left": ("nil", "0"),
        "right": ("nil", "0"),
        "insideH": ("nil", "0"),
        "insideV": ("nil", "0"),
    }
    for edge, (value, size) in settings.items():
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), value)
        node.set(qn("w:sz"), size)
        node.set(qn("w:color"), "000000")


def replace_equation_table_with_paragraph(table) -> None:
    """Convert a two-cell equation layout table to an accessible tabbed paragraph."""
    label = table.cell(0, 1).text.strip()
    source = table.cell(0, 0).paragraphs[0]._p
    paragraph_xml = OxmlElement("w:p")
    table._tbl.addprevious(paragraph_xml)
    paragraph = Paragraph(paragraph_xml, table._parent)
    paragraph.paragraph_format.tab_stops.add_tab_stop(
        Inches(3.25), WD_TAB_ALIGNMENT.CENTER
    )
    paragraph.paragraph_format.tab_stops.add_tab_stop(
        Inches(6.5), WD_TAB_ALIGNMENT.RIGHT
    )
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_together = True

    opening_tab = paragraph.add_run("\t")
    set_run_font(opening_tab, size=10)
    for child in source:
        if child.tag != qn("w:pPr"):
            paragraph._p.append(deepcopy(child))
    label_run = paragraph.add_run(f"\t{label}")
    set_run_font(label_run, size=10)

    table._tbl.getparent().remove(table._tbl)


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    fld_char_1 = OxmlElement("w:fldChar")
    fld_char_1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = "PAGE"
    fld_char_2 = OxmlElement("w:fldChar")
    fld_char_2.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char_1, instr_text, fld_char_2])


def set_run_font(run, name="Times New Roman", size=None, bold=None, italic=None, color=None) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def format_style(style, font="Times New Roman", size=10.5, color="000000", bold=False, italic=False):
    style.font.name = font
    style._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string(color)
    style.font.bold = bold
    style.font.italic = italic


def ensure_style(doc, name, base="Normal"):
    styles = doc.styles
    if name in styles:
        return styles[name]
    st = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    st.base_style = styles[base]
    return st


def style_document(doc: Document) -> None:
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin = Inches(1.0)
    sec.right_margin = Inches(1.0)
    sec.header_distance = Inches(0.35)
    sec.footer_distance = Inches(0.35)
    sec.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    format_style(normal, size=10)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing = 2.0
    normal.paragraph_format.space_after = Pt(3)
    normal.paragraph_format.widow_control = True

    title = doc.styles["Title"]
    format_style(title, size=16, color=NAVY, bold=True)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(8)
    title.paragraph_format.keep_with_next = True

    if "Subtitle" in doc.styles:
        subtitle = doc.styles["Subtitle"]
        format_style(subtitle, size=10.5, color=MID_GRAY)
        subtitle.paragraph_format.space_after = Pt(5)

    for name, size, color in (
        ("Heading 1", 13, NAVY),
        ("Heading 2", 11, BLUE),
        ("Heading 3", 10, NAVY),
    ):
        if name in doc.styles:
            st = doc.styles[name]
            format_style(st, size=size, color=color, bold=True, italic=(name == "Heading 3"))
            st.paragraph_format.space_before = Pt(11 if name == "Heading 1" else 8)
            st.paragraph_format.space_after = Pt(4)
            st.paragraph_format.keep_with_next = True
            st.paragraph_format.keep_together = True

    caption = ensure_style(doc, "Caption")
    format_style(caption, size=8.5, color="343A40", italic=True)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(3)
    caption.paragraph_format.space_after = Pt(8)
    caption.paragraph_format.keep_together = True

    quote = doc.styles["Block Text"] if "Block Text" in doc.styles else ensure_style(doc, "Block Text")
    format_style(quote, size=9.5, color="343A40", italic=True)
    quote.paragraph_format.left_indent = Inches(0.3)
    quote.paragraph_format.right_indent = Inches(0.2)

    # Running header: compact journal-manuscript override of the memo masthead.
    header = sec.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.tab_stops.add_tab_stop(Inches(6.45), WD_TAB_ALIGNMENT.RIGHT)
    r = hp.add_run("MEASUREMENT-BASED AUDIT OF NEURALFOIL")
    set_run_font(r, name="Arial", size=7.5, bold=True, color=MID_GRAY)
    r = hp.add_run("\t")
    set_run_font(r, name="Arial", size=7.5, color=MID_GRAY)
    add_page_field(hp)
    for rr in hp.runs:
        if rr.text != "MEASUREMENT-BASED AUDIT OF NEURALFOIL":
            set_run_font(rr, name="Arial", size=7.5, color=MID_GRAY)
    ppr = hp._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), "B8C6D9")
    pbdr.append(bottom)
    ppr.append(pbdr)

    first_header = sec.first_page_header
    first_header.paragraphs[0].text = ""

    footer = sec.footer
    footer.paragraphs[0].text = ""

    # Paragraph-level cleanup.
    reference_mode = False
    appendix_mode = False
    before_abstract = True
    for p in doc.paragraphs:
        text = p.text.strip()
        if before_abstract and p.style.name != "Title":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if before_abstract and p.style.name == "Title":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if before_abstract and text.startswith("Kaan Boge"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if before_abstract and text.startswith("Article type:"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if text == "Abstract":
            before_abstract = False

        if text == "Nomenclature":
            p.paragraph_format.page_break_before = True

        if text == "References":
            reference_mode = True
        elif text.startswith("Appendix A"):
            appendix_mode = True
        elif text in {"Data and Code Availability", "Author Contributions"}:
            p.paragraph_format.keep_with_next = True

        if reference_mode and text and re.match(r"^\[\d+\]", text):
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 2.0
            for run in p.runs:
                set_run_font(run, size=10)

        if re.match(r"^Table\s+(?:[A-Z]\d+|\d+)\.", text) and p.style.name != "Caption":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(7)
            p.paragraph_format.space_after = Pt(3)
            # LibreOffice can lose the body of a table when an appendix table
            # begins with only its repeated header at the foot of a page.
            # C1 is the affected boundary in this manuscript, so start it on a
            # fresh page and preserve the complete four-row table.
            if text.startswith("Table C1."):
                p.paragraph_format.page_break_before = True
            for run in p.runs:
                set_run_font(run, size=8.8, bold=True, color=NAVY)

        if p.style.name.startswith("Heading"):
            p.paragraph_format.keep_with_next = True

        # Prevent lonely equations/captions and excessive figure whitespace.
        if p._p.xpath(".//m:oMathPara"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_together = True
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)

    # Equations use center and right tab stops rather than layout tables. This
    # preserves flush-right numbering without creating false table semantics.
    # Data tables then receive full-width scientific styling and repeated headers.
    for table in list(doc.tables):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        equation_layout = (
            len(table.rows) == 1
            and len(table.columns) == 2
            and re.fullmatch(r"\(\d+[a-z]?\)", table.cell(0, 1).text.strip()) is not None
        )
        if equation_layout:
            replace_equation_table_with_paragraph(table)
            continue

        table.autofit = True
        table.allow_autofit = True
        set_aiaa_table_borders(table)
        if table.rows:
            for cell in table.rows[0].cells:
                if cell._tc.xpath(".//m:oMath | .//m:oMathPara"):
                    raise ValueError(
                        "Math is not permitted in dark table-header cells; use a plain-text header "
                        "or add explicit OMML color handling before publication."
                    )
            repeat_table_header(table.rows[0])
        for i, row in enumerate(table.rows):
            cant_split(row)
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                set_cell_margins(cell)
                set_cell_shading(cell, "FFFFFF")
                if i == 0:
                    set_cell_border(cell, "bottom", value="single", size=6)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(1.5)
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.line_spacing = 1.0
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for run in p.runs:
                        set_run_font(
                            run,
                            size=8.0,
                            bold=(i == 0),
                            color="000000",
                        )

    # Make inline images predictable and centered.
    for p in doc.paragraphs:
        if p._p.xpath(".//w:drawing"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_together = True
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(2)

    props = doc.core_properties
    props.title = "Measurement-Based Audit of NeuralFoil Accuracy and Trust Signals"
    props.subject = "Final evidence-audited aerospace surrogate-model benchmark manuscript"
    props.author = "Kaan Boge"
    props.keywords = "NeuralFoil, XFOIL, airfoil, validation, reproducibility, transonic"


def main() -> None:
    doc = Document(DOCX)
    style_document(doc)
    doc.save(DOCX)
    print(DOCX)


if __name__ == "__main__":
    main()
