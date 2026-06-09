# Export szolgáltatások – PDF, XLSX, CSV és könyvelői adatlap generálása
import csv
import io
from datetime import date
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from models.result import InvoiceResult, InvoiceStatus
from utils.logger import get_logger

logger = get_logger(__name__)

# Státusz szövegek magyarítása
STATUS_LABELS = {
    InvoiceStatus.OK: "Rendben",
    InvoiceStatus.WARNING: "Figyelmeztetés",
    InvoiceStatus.ERROR: "Hiba",
}

# Státusz ikonok PDF-hez
STATUS_ICONS = {
    InvoiceStatus.OK: "✅",
    InvoiceStatus.WARNING: "⚠️",
    InvoiceStatus.ERROR: "❌",
}

# Cellaszínek XLSX-hez (RGB hex)
STATUS_COLORS = {
    InvoiceStatus.OK: "C6EFCE",        # Zöld
    InvoiceStatus.WARNING: "FFEB9C",   # Sárga
    InvoiceStatus.ERROR: "FFC7CE",     # Piros
}


def _format_amount(value) -> str:
    """Pénzösszeg formázása két tizedesjeggyel."""
    if value is None:
        return ""
    return f"{value:,.2f}"


def _format_date(value) -> str:
    """Dátum formázása ÉÉÉÉ-HH-NN formátumba."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def generate_pdf(results: List[InvoiceResult]) -> bytes:
    """
    PDF riport generálása a feldolgozott számlákról.
    Tartalmazza az összesítő táblázatot és az egyedi részleteket.

    Args:
        results: A feldolgozott számlák eredménylistája

    Returns:
        bytes: A generált PDF fájl tartalma
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Fejléc
    elements.append(Paragraph("Intelligens Számlafeldolgozó – Riport", styles["Title"]))
    elements.append(Paragraph(f"Generálva: {date.today().strftime('%Y-%m-%d')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Összesítő táblázat fejléce
    table_data = [["Fájlnév", "Eladó", "Bruttó összeg", "Pénznem", "Státusz"]]

    for result in results:
        inv = result.invoice_data
        row = [
            result.file_name,
            (inv.supplier_name or "") if inv else "",
            _format_amount(inv.gross_amount if inv else None),
            (inv.currency or "") if inv else "",
            f"{STATUS_ICONS.get(result.status, '')} {STATUS_LABELS.get(result.status, '')}",
        ]
        table_data.append(row)

    # Táblázat stílus
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 1 * cm))

    # Részletes szekciók számlánként
    for result in results:
        elements.append(Paragraph(f"Számla: {result.file_name}", styles["Heading2"]))

        if result.invoice_data:
            inv = result.invoice_data
            details = [
                ["Eladó neve:", inv.supplier_name or "–"],
                ["Eladó adószáma:", inv.supplier_tax_id or "–"],
                ["Vevő neve:", inv.buyer_name or "–"],
                ["Nettó összeg:", _format_amount(inv.net_amount)],
                ["ÁFA összeg:", _format_amount(inv.vat_amount)],
                ["Bruttó összeg:", _format_amount(inv.gross_amount)],
                ["Pénznem:", inv.currency or "–"],
                ["Számla kelte:", _format_date(inv.invoice_date)],
                ["Fizetési határidő:", _format_date(inv.due_date)],
            ]
            detail_table = Table(details, colWidths=[5 * cm, 10 * cm])
            detail_table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]))
            elements.append(detail_table)

        # Validációs hibák listázása
        if result.issues:
            elements.append(Paragraph("Validációs megjegyzések:", styles["Heading3"]))
            for issue in result.issues:
                icon = STATUS_ICONS.get(issue.severity, "")
                elements.append(Paragraph(
                    f"{icon} {issue.message}",
                    styles["Normal"]
                ))

        # Gemini könyvelői összefoglaló
        if result.gemini_summary:
            elements.append(Paragraph("Könyvelői értékelés:", styles["Heading3"]))
            elements.append(Paragraph(result.gemini_summary, styles["Normal"]))

        elements.append(Spacer(1, 0.5 * cm))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(f"PDF generálva: {len(results)} számla, {len(pdf_bytes)} byte")
    return pdf_bytes


def generate_xlsx(results: List[InvoiceResult]) -> bytes:
    """
    Általános XLSX export generálása két munkalapon.
    1. munkalap: Összesítő táblázat
    2. munkalap: Tételsorok

    Args:
        results: A feldolgozott számlák eredménylistája

    Returns:
        bytes: A generált XLSX fájl tartalma
    """
    wb = openpyxl.Workbook()

    # --- 1. munkalap: Összesítő ---
    ws_summary = wb.active
    ws_summary.title = "Összesítő"

    # Fejléc sor
    headers = [
        "Fájlnév", "Eladó neve", "Eladó adószám", "Vevő neve",
        "Nettó összeg", "ÁFA összeg", "Bruttó összeg", "Pénznem",
        "Számla kelte", "Fizetési határidő", "Teljesítés dátuma", "Státusz",
    ]
    ws_summary.append(headers)

    # Fejléc formázás
    for col_num, _ in enumerate(headers, 1):
        cell = ws_summary.cell(row=1, column=col_num)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Adatsorok
    for result in results:
        inv = result.invoice_data
        row = [
            result.file_name,
            (inv.supplier_name or "") if inv else "",
            (inv.supplier_tax_id or "") if inv else "",
            (inv.buyer_name or "") if inv else "",
            inv.net_amount if inv else None,
            inv.vat_amount if inv else None,
            inv.gross_amount if inv else None,
            (inv.currency or "") if inv else "",
            inv.invoice_date if inv else None,
            inv.due_date if inv else None,
            inv.completion_date if inv else None,
            STATUS_LABELS.get(result.status, ""),
        ]
        ws_summary.append(row)

        # Státusz alapú sorszínezés
        fill_color = STATUS_COLORS.get(result.status, "FFFFFF")
        row_num = ws_summary.max_row
        for col_num in range(1, len(headers) + 1):
            ws_summary.cell(row=row_num, column=col_num).fill = PatternFill(
                start_color=fill_color, end_color=fill_color, fill_type="solid"
            )

    # Fejléc rögzítése és AutoFilter
    ws_summary.freeze_panes = "A2"
    ws_summary.auto_filter.ref = ws_summary.dimensions

    # --- 2. munkalap: Tételsorok ---
    ws_items = wb.create_sheet(title="Tételsorok")
    item_headers = ["Fájlnév", "Eladó neve", "Tétel leírás", "Mennyiség", "Egységár", "Összeg"]
    ws_items.append(item_headers)

    for col_num, _ in enumerate(item_headers, 1):
        cell = ws_items.cell(row=1, column=col_num)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    for result in results:
        if result.invoice_data and result.invoice_data.line_items:
            for item in result.invoice_data.line_items:
                ws_items.append([
                    result.file_name,
                    result.invoice_data.supplier_name or "",
                    item.description or "",
                    item.quantity,
                    item.unit_price,
                    item.total,
                ])

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()
    buffer.close()

    logger.info(f"XLSX generálva: {len(results)} számla")
    return xlsx_bytes


def generate_csv(results: List[InvoiceResult]) -> bytes:
    """
    CSV export generálása (UTF-8 BOM, Excel kompatibilis).
    Egy sor = egy számla, összes mező oszlopként.

    Args:
        results: A feldolgozott számlák eredménylistája

    Returns:
        bytes: A generált CSV fájl tartalma (UTF-8 BOM kódolással)
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # Fejléc sor
    headers = [
        "Fájlnév", "Eladó neve", "Eladó adószám", "Eladó cím",
        "Vevő neve", "Vevő adószám",
        "Nettó összeg", "ÁFA összeg", "ÁFA kulcs", "Bruttó összeg", "Pénznem",
        "Számla száma", "Számla kelte", "Fizetési határidő", "Teljesítés dátuma",
        "Státusz", "Könyvelői megjegyzés",
    ]
    writer.writerow(headers)

    # Adatsorok
    for result in results:
        inv = result.invoice_data
        row = [
            result.file_name,
            (inv.supplier_name or "") if inv else "",
            (inv.supplier_tax_id or "") if inv else "",
            (inv.supplier_address or "") if inv else "",
            (inv.buyer_name or "") if inv else "",
            (inv.buyer_tax_id or "") if inv else "",
            inv.net_amount if inv else "",
            inv.vat_amount if inv else "",
            inv.vat_rate if inv else "",
            inv.gross_amount if inv else "",
            (inv.currency or "") if inv else "",
            (inv.invoice_number or "") if inv else "",
            _format_date(inv.invoice_date if inv else None),
            _format_date(inv.due_date if inv else None),
            _format_date(inv.completion_date if inv else None),
            STATUS_LABELS.get(result.status, ""),
            (result.gemini_summary or "") if result.gemini_summary else "",
        ]
        writer.writerow(row)

    # UTF-8 BOM hozzáadása az Excel kompatibilitásért
    csv_content = buffer.getvalue()
    buffer.close()

    logger.info(f"CSV generálva: {len(results)} számla")
    return b"\xef\xbb\xbf" + csv_content.encode("utf-8")


def generate_xlsx_accounting(results: List[InvoiceResult]) -> bytes:
    """
    Könyvelői adatlap XLSX export generálása.
    Rögzített oszlopszerkezet, fejléc rögzítve, AutoFilter bekapcsolva.
    Fájlnév formátum: szamlak_konyvelo_YYYYMMDD.xlsx

    Args:
        results: A feldolgozott számlák eredménylistája

    Returns:
        bytes: A generált XLSX fájl tartalma
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Könyvelői adatlap"

    # Kötelező oszlopsorrend a specifikáció szerint
    headers = [
        "Ügyfél neve",          # supplier_name
        "Ügyfél címe",          # supplier_address
        "Adószám",              # supplier_tax_id
        "Nettó összeg",         # net_amount
        "Bruttó összeg",        # gross_amount
        "ÁFA összeg",           # vat_amount
        "Fizetési határidő",    # due_date
        "Kelt",                 # invoice_date
        "Teljesítés dátuma",    # completion_date
        "Pénznem",              # currency
        "Státusz",              # status
    ]
    ws.append(headers)

    # Fejléc formázás
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Adatsorok
    for result in results:
        inv = result.invoice_data
        row = [
            (inv.supplier_name or None) if inv else None,
            (inv.supplier_address or None) if inv else None,
            (inv.supplier_tax_id or None) if inv else None,
            inv.net_amount if inv else None,
            inv.gross_amount if inv else None,
            inv.vat_amount if inv else None,
            inv.due_date if inv else None,
            inv.invoice_date if inv else None,
            inv.completion_date if inv else None,
            (inv.currency or None) if inv else None,
            STATUS_LABELS.get(result.status, ""),
        ]
        ws.append(row)

        # Státusz alapú sorszínezés
        fill_color = STATUS_COLORS.get(result.status, "FFFFFF")
        row_num = ws.max_row
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.fill = PatternFill(
                start_color=fill_color, end_color=fill_color, fill_type="solid"
            )
            # None értékek helyett üres cella (ne jelenjen meg "None" szöveg)
            if cell.value is None:
                cell.value = ""

    # Fejléc rögzítése (freeze panes) és AutoFilter
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Oszlopszélességek beállítása
    column_widths = [25, 35, 18, 15, 15, 15, 18, 18, 18, 10, 16]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()
    buffer.close()

    logger.info(f"Könyvelői XLSX generálva: {len(results)} számla")
    return xlsx_bytes
