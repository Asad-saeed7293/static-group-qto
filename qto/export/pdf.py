"""Client-ready tender PDF - the Static Group BOQ as a document you can email, not just a spreadsheet.

Built from the exact same row layout as the in-app preview and the Excel export (preview_static_boq in
excel.py), so the PDF, the preview and the download can never show three different structures. RATE and
AMOUNT are left blank throughout: no priced rate exists anywhere in this system for any item (the real
Static Group historical BOQs this project was modelled on are themselves unpriced until an estimator
fills them in after export), so printing a number there would be a fabricated price, not a real one.
"""
from __future__ import annotations

import os
from xml.sax.saxutils import escape as _esc

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import store
from .excel import preview_static_boq

NAVY = colors.HexColor("#1F3A5F")
STEEL = colors.HexColor("#3E6C9C")
PALE = colors.HexColor("#EEF2F7")
INK = colors.HexColor("#1F2937")
GREY = colors.HexColor("#6B7280")
LOGO = os.path.join(store.ROOT, "web", "brand", "static-logo.png")

COL_WIDTHS = [18 * mm, 86 * mm, 18 * mm, 16 * mm, 20 * mm, 28 * mm]


def _styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, textColor=NAVY, spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=10, spaceAfter=4),
        "kv_label": ParagraphStyle("kv_label", fontName="Helvetica-Bold", fontSize=9.5, textColor=GREY),
        "kv_val": ParagraphStyle("kv_val", fontName="Helvetica", fontSize=10.5, textColor=INK),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=9, textColor=GREY, spaceBefore=6),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11),
        "cell_b": ParagraphStyle("cell_b", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY, leading=11),
        "sug": ParagraphStyle("sug", fontName="Helvetica-Oblique", fontSize=8.5, textColor=colors.HexColor("#946F00"), leading=11),
    }


def _header_block(sty, title, preview):
    rows = []
    if os.path.exists(LOGO):
        rows.append(Image(LOGO, width=42 * mm, height=42 * mm * 0.28, kind="proportional"))
    rows.append(Spacer(1, 6))
    rows.append(Paragraph(_esc(title), sty["title"]))
    p = preview["project"]
    meta = preview["boq_meta"]
    kv = [["Project:", p["name"]], ["Client:", p.get("client") or "-"], ["Location:", p.get("location") or "-"],
          ["Ref. No:", meta.get("ref") or "-"], ["Date:", meta.get("date") or "-"]]
    t = Table([[Paragraph(_esc(k), sty["kv_label"]), Paragraph(_esc(v), sty["kv_val"])] for k, v in kv], colWidths=[26 * mm, 140 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    rows.append(t)
    rows.append(Spacer(1, 10))
    return rows


def _boq_table(sty, sheet_rows):
    header = [Paragraph(h, ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.white))
              for h in ("ITEM", "DESCRIPTION", "QTY", "UNIT", "RATE", "AMOUNT (QR)")]
    data = [header]
    row_styles = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    for i, r in enumerate(sheet_rows, start=1):
        if r["row"] in ("section", "subsection"):
            data.append([Paragraph(_esc(r["code"]), sty["cell_b"]), Paragraph(_esc(r["title"]), sty["cell_b"]), "", "", "", ""])
            row_styles.append(("BACKGROUND", (0, i), (-1, i), PALE))
            row_styles.append(("SPAN", (1, i), (5, i)))
        elif r["row"] == "group":
            data.append(["", Paragraph(f"{_esc(r['code'])}&nbsp;&nbsp;{_esc(r['title'])}", sty["cell_b"]), "", "", "", ""])
            row_styles.append(("SPAN", (1, i), (5, i)))
        elif r["row"] == "subtotal":
            data.append(["", Paragraph("TOTAL CARRIED TO SUMMARY", sty["cell_b"]), "", "", "", Paragraph("-", sty["cell_b"])])
            row_styles.append(("SPAN", (1, i), (4, i)))
            row_styles.append(("LINEABOVE", (0, i), (-1, i), 0.6, STEEL))
        else:
            qty = f"{r['quantity']:,.2f}" if r["quantity"] is not None else "-"
            sr = r.get("suggested_rate")
            if sr is not None:
                rate_p = Paragraph(f"{sr:,.2f}*", sty["sug"])
                amt = sr * r["quantity"] if r["quantity"] is not None else None
                amt_p = Paragraph(f"{amt:,.2f}*" if amt is not None else "-", sty["sug"])
            else:
                rate_p, amt_p = Paragraph("-", sty["cell"]), Paragraph("-", sty["cell"])
            data.append([Paragraph(_esc(r["code"]), sty["cell"]), Paragraph(_esc(r["description"]), sty["cell"]),
                        Paragraph(qty, sty["cell"]), Paragraph(_esc(r.get("unit") or ""), sty["cell"]),
                        rate_p, amt_p])
    row_styles += [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                   ("ALIGN", (2, 1), (2, -1), "RIGHT"), ("ALIGN", (4, 1), (5, -1), "RIGHT")]
    t = Table(data, colWidths=COL_WIDTHS, repeatRows=1)
    t.setStyle(TableStyle(row_styles))
    return t


def export_tender_pdf(pid, path):
    """A single, client-ready PDF: cover + one section per sheet + summary - same structure as the Excel
    export and the in-app preview. RATE/AMOUNT print as '-' unless rate memory (qto/knowledge/rates.py)
    has a real rate from a past priced BOQ - then they print in amber italics with a trailing '*',
    clearly marked as a suggestion to review, never a confirmed price."""
    preview = preview_static_boq(pid)
    has_suggestions = any(r.get("suggested_rate") is not None for rows in preview["sheets"].values() for r in rows)
    sty = _styles()
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
                             title=f"{preview['title']} - Tender BOQ", author="Static Group")
    story = []
    story += _header_block(sty, preview["title"], preview)
    note = ("Rates and amounts are to be completed by Static Group Estimating. All quantities below are "
            "calculated from the project drawings - every line that could not be proven from the drawings is "
            "marked separately and is not included here as a guessed figure.")
    if has_suggestions:
        note += (" Rates shown in <i>amber italics with a trailing *</i> are suggestions from rate memory - the "
                 "most recent rate Static Group entered for that item on a past priced project - and must be "
                 "reviewed before this BOQ is priced; they are not confirmed.")
    story.append(Paragraph(note, sty["note"]))
    story.append(PageBreak())

    for sheet in preview["sheet_order"]:
        rows = preview["sheets"].get(sheet) or []
        if not rows:
            continue
        story.append(Paragraph(_esc(sheet), sty["h2"]))
        story.append(_boq_table(sty, rows))
        story.append(PageBreak())

    if preview["summary"]:
        story.append(Paragraph("Summary", sty["h2"]))
        head = [Paragraph(h, ParagraphStyle("th2", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white))
                for h in ("ITEM", "DESCRIPTION", "AMOUNT (QR)")]
        srows = [head]
        for s in preview["summary"]:
            srows.append([Paragraph(_esc(s["code"]), sty["cell_b"]), Paragraph(_esc(s["title"]), sty["cell_b"]), Paragraph("-", sty["cell_b"])])
        srows.append(["", Paragraph("GRAND TOTAL (QR)", sty["cell_b"]), Paragraph("-", sty["cell_b"])])
        t = Table(srows, colWidths=[18 * mm, 140 * mm, 28 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")),
                               ("LINEABOVE", (0, -1), (-1, -1), 0.8, NAVY), ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.append(t)

    doc.build(story)
    return path
