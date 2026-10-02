"""Build docs/documentation.pdf.

Schedule values, figures and EMANE results are read from the project itself
(src/, data/grid16.json, emane/out/), so the document cannot drift from the code.

    pip install reportlab
    python docs/build/build_documentation.py
"""
import json
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "emane"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge
import figures
from cli import parse_coords
from content import AUTHOR, DATE, sections
from graph_engine import build_physical_graph, frame_length, slot_lower_bound

INK, SECONDARY, MUTED = figures.INK, figures.SECONDARY, figures.MUTED
RULE = HexColor("#e1e0d9")
CODE_FILL = HexColor("#f4f4f2")

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK,
                      spaceAfter=7, alignment=TA_LEFT)
STYLES = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=INK),
    "subtitle": ParagraphStyle("subtitle", parent=BODY, fontSize=11, leading=15, textColor=SECONDARY,
                               spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK,
                         spaceBefore=14, spaceAfter=7),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=INK,
                         spaceBefore=8, spaceAfter=4),
    "body": BODY,
    "bullet": ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=4),
    "caption": ParagraphStyle("caption", parent=BODY, fontSize=8.5, leading=11.5, textColor=SECONDARY,
                              spaceAfter=10),
    "cell": ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12, spaceAfter=0),
    "cellhead": ParagraphStyle("cellhead", parent=BODY, fontName="Helvetica-Bold", fontSize=9,
                               leading=12, spaceAfter=0),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=7.6, leading=9.6, textColor=INK,
                           backColor=CODE_FILL, borderPadding=6, leftIndent=6, rightIndent=6,
                           spaceBefore=4, spaceAfter=12),
}


def table(rows, widths, header=True):
    """rows of strings -> a ruled table whose cells wrap."""
    cells = [[Paragraph(str(value), STYLES["cellhead" if header and r == 0 else "cell"])
              for value in row] for r, row in enumerate(rows)]
    result = Table(cells, colWidths=[w * mm for w in widths], hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]
    if header:
        style.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, MUTED))
    result.setStyle(TableStyle(style))
    return result


def side_by_side(left, right, widths):
    result = Table([[left, right]], colWidths=[w * mm for w in widths], hAlign="LEFT")
    result.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return result


def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(22 * mm, 12 * mm, "TDMA Schedule Optimizer: project documentation")
    canvas.drawRightString(A4[0] - 22 * mm, 12 * mm, f"Page {document.page}")
    canvas.restoreState()


def load_results():
    """EMANE run summaries, keyed by schedule name; empty if the demo has not been run."""
    results = {}
    for path in sorted((ROOT / "emane" / "out").glob("*/summary.json")):
        results[path.parent.name] = json.loads(path.read_text())
    return results


def main():
    coords = parse_coords((ROOT / "data" / "grid16.json").read_text())
    graph = build_physical_graph(coords)
    slots = bridge.optimise(coords)
    facts = {
        "coords": coords,
        "graph": graph,
        "slots": slots,
        "frame": frame_length(slots),
        "bound": slot_lower_bound(graph),
        "results": load_results(),
        "schedule_xml": bridge.schedule_xml(slots),
    }
    helpers = {
        "P": lambda text, style="body": Paragraph(text, STYLES[style]),
        "bullets": lambda items: [Paragraph(item, STYLES["bullet"], bulletText="•") for item in items],
        "code": lambda text: Preformatted(text.strip("\n"), STYLES["code"]),
        "table": table,
        "side_by_side": side_by_side,
        "gap": lambda height=6: Spacer(1, height),
        "keep": KeepTogether,
        "page_break": PageBreak,
        "figures": figures,
    }
    story = [
        Paragraph("TDMA Schedule Optimizer", STYLES["title"]),
        Spacer(1, 4),
        Paragraph(f"Project documentation: design process, reasoning and final values for "
                  f"Part 1 and Part 2<br/>{AUTHOR} · {DATE}", STYLES["subtitle"]),
    ]
    story += sections(facts, helpers)

    output = ROOT / "docs" / "documentation.pdf"
    document = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                                 topMargin=20 * mm, bottomMargin=20 * mm,
                                 title="TDMA Schedule Optimizer: project documentation", author=AUTHOR)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == "__main__":
    main()
