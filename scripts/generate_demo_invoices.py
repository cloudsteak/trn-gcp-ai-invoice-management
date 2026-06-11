#!/usr/bin/env python3
"""Fiktív demó számlák generálása az invoices/ mappába (oktatási cél)."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

INVOICES_DIR = Path(__file__).resolve().parent.parent / "invoices"

DISCLAIMER = (
    "DEMO - NOT A REAL INVOICE. Fictitious data for training and testing only. "
    "Not valid for accounting, tax reporting, or payment."
)


def _draw_pdf(path: Path, title: str, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 2 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, DISCLAIMER)
    y -= 1.2 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, title)
    y -= 1 * cm
    c.setFont("Helvetica", 11)
    for line in lines:
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 11)
        c.drawString(2 * cm, y, line)
        y -= 0.55 * cm
    c.save()


def generate_english_invoice() -> None:
    lines = [
        "Supplier: Nordic Cloud Supplies Ltd.",
        "Address: 14 Demo Street, Helsinki, FI-00100",
        "Tax ID: FI12345678",
        "Bank: FI21 1234 5600 0007 85",
        "",
        "Customer: Cloudsteak Training Kft.",
        "Address: 1051 Budapest, Demo Square 1.",
        "Tax ID: 12345678-2-41",
        "",
        "Invoice No: DEMO-EN-2026-001",
        "Invoice date: 2026-06-10",
        "Due date: 2026-06-24",
        "Completion date: 2026-06-10",
        "Currency: EUR",
        "",
        "Description                    Qty   Unit price   Net     VAT 27%   Gross",
        "Cloud AI workshop materials      1    400.00 EUR  400.00   108.00   508.00",
        "Training documentation           1    100.00 EUR  100.00    27.00   127.00",
        "",
        "Net total:   500.00 EUR",
        "VAT total:   135.00 EUR",
        "Gross total: 635.00 EUR",
        "Amount due:  635.00 EUR",
        "",
        "All names, addresses, and tax IDs in this document are fictitious.",
    ]
    _draw_pdf(INVOICES_DIR / "szamla_ok_en.pdf", "INVOICE - DEMO VALID SAMPLE", lines)


def generate_handwritten_jpg() -> None:
    if Image is None:
        print("Pillow nincs telepítve – szamla_kezzel_irt.jpg kihagyva.")
        return

    img = Image.new("RGB", (900, 1200), color=(255, 252, 240))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", 28)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
        small = font

    y = 40
    for text, fnt in [
        ("DEMO – kézzel írt fiktív számla", font),
        ("(oktatási teszt – NEM valódi bizonylat)", small),
        ("", small),
        ("Eladó: Kovács Péter egyéni vállalkozó", font),
        ("Cím: 6000 Kecskemét, Szőlő utca 3.", small),
        ("", small),
        ("Vevő: Demo Vásárló Kft.", small),
        ("", small),
        ("Számla sorszám: KEZI-2026-99", small),
        ("Kelte: 2026.06.08", small),
        ("Fizetési határidő: 2026.06.18", small),
        ("", small),
        ("Tétel: Kerti munka – 8 óra", small),
        ("Nettó: 32 000 Ft", small),
        ("ÁFA 27%: 8 640 Ft", small),
        ("Fizetendő: 40 640 Ft", small),
        ("", small),
        ("Megjegyzés: adószám nincs feltüntetve", small),
        ("(szándékos hiány – Gemini hibát várunk)", small),
    ]:
        draw.text((40, y), text, fill=(20, 20, 80), font=fnt)
        y += 36 if fnt == font else 30

    img.save(INVOICES_DIR / "szamla_kezzel_irt.jpg", format="JPEG", quality=92, optimize=True)


def main() -> None:
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
    generate_english_invoice()
    generate_handwritten_jpg()
    print(f"Generálva: {INVOICES_DIR}")


if __name__ == "__main__":
    main()
