"""Record PDF navigation, font embedding, page geometry and artifact identity.

Use --write-page-map on a provisional rendering, then rebuild the DOCX with that
map. Run again on the final PDF to confirm stable navigation. Visual inspection
of the rendered pages is a separate requirement, not replaced by these checks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader
import pdfplumber

ROOT=Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("pdf",type=Path)
    parser.add_argument("--write-page-map",action="store_true")
    args=parser.parse_args()
    reader=PdfReader(args.pdf)
    headings=json.loads((ROOT/"work/headings.json").read_text())
    selected=[h["text"] for h in headings if h["level"]==1 and
              (h["text"].startswith(("1 ","2 ","3 ","4 ","5 ","6 ","Appendix ")) or h["text"]=="References")]
    outline={}
    def visit(items):
        for item in items:
            if isinstance(item,list): visit(item)
            else: outline[item.title]=reader.get_destination_page_number(item)+1
    visit(reader.outline)
    actual={title:outline[title] for title in selected}
    mapfile=ROOT/"work/page_map.json"
    if args.write_page_map:
        mapfile.write_text(json.dumps(actual,indent=2)+"\n")
    expected=json.loads(mapfile.read_text())
    fonts={}
    bad_boxes=[]
    blank_pages=[]
    links=0
    out_of_bounds=[]
    with pdfplumber.open(args.pdf) as pdf:
        for i,page in enumerate(pdf.pages,1):
            for char in page.chars:
                if char.get("text","").strip() and (char["x0"] < 0 or char["x1"] > page.width+0.5 or char["top"] < -0.5 or char["bottom"] > page.height+0.5):
                    out_of_bounds.append({"page":i,"text":char["text"],"bbox":[char["x0"],char["top"],char["x1"],char["bottom"]]})
    for i,page in enumerate(reader.pages,1):
        if tuple(float(x) for x in page.mediabox)!=(0.0,0.0,612.0,792.0): bad_boxes.append(i)
        if len(page.extract_text().strip())<75: blank_pages.append(i)
        links+=sum(1 for a in page.get("/Annots",[]) if a.get_object().get("/Subtype")=="/Link")
        for ref in page.get("/Resources",{}).get("/Font",{}).values():
            f=ref.get_object()
            descendants=f.get("/DescendantFonts",[f])
            for descendant in descendants:
                ff=descendant.get_object()
                descriptor=ff.get("/FontDescriptor")
                desc=descriptor.get_object() if descriptor else {}
                name=str(ff.get("/BaseFont",f.get("/BaseFont","unknown")))
                fonts[name]=any(k in desc for k in ("/FontFile","/FontFile2","/FontFile3"))
    checks={"navigation_stable":actual==expected,"letter_page_geometry":not bad_boxes,
            "no_empty_pages":not blank_pages,"all_pdf_fonts_embedded":bool(fonts) and all(fonts.values()),
            "navigation_and_reference_links_present":links>=15,
            "all_text_glyphs_within_page":not out_of_bounds,
            "all_selected_headings_mapped":len(actual)==15}
    report={"checks":checks,"page_count":len(reader.pages),"page_map":actual,
            "fonts":fonts,"pdf_link_annotations":links,"blank_pages":blank_pages,
            "out_of_bounds_text":out_of_bounds,
            "pdf_sha256":digest(args.pdf),
            "docx_sha256":digest(ROOT/"output/docx/NeuralFoil_Research_Paper.docx"),
            "visual_qa":"Required separately; this script does not certify page appearance."}
    (ROOT/"work/layout_qa.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if not all(checks.values()): raise SystemExit(1)

if __name__=="__main__": main()
