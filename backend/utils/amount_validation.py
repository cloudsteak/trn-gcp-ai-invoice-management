# Összeg-konzisztencia ellenőrzés – nettó + ÁFA = bruttó, bruttó = fizetendő
import re

from models.invoice import InvoiceData
from models.result import InvoiceStatus, ValidationIssue

# HUF egész forint – 1 Ft tolerancia kerekítés miatt
_AMOUNT_TOLERANCE = 1.0

# Magyar számlák tipikus összesítő sorai (OCR / PDF szöveg)
_LABEL_PATTERNS: dict[str, list[str]] = {
    "net": [
        r"Nettó összesen:\s*([\d\s]+)",
        r"Nettó összesen\s+([\d\s]+)",
    ],
    "vat": [
        r"ÁFA összesen:\s*([\d\s]+)",
        r"ÁFA összesen\s+([\d\s]+)",
    ],
    "gross": [
        r"Bruttó összesen:\s*([\d\s]+)",
        r"Bruttó összesen\s+([\d\s]+)",
    ],
    "amount_due": [
        r"Fizetendő:\s*([\d\s]+)",
        r"Fizetendő\s+([\d\s]+)",
        r"Amount due:\s*([\d\s.,]+)",
    ],
}


def _parse_amount(value: str) -> float | None:
    """Magyar formátumú összeg parse – pl. '65 000' vagy '65.000,00'."""
    if not value:
        return None
    cleaned = value.strip().replace("\u00a0", " ").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_labeled_amount(text: str, patterns: list[str]) -> float | None:
    """Összeg kinyerése címke alapján a nyers számlaszövegből."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            amount = _parse_amount(match.group(1))
            if amount is not None:
                return amount
    return None


def _fmt_ft(amount: float) -> str:
    """Összeg megjelenítése magyar számlán (pl. 65 000 Ft)."""
    return f"{int(round(amount)):,}".replace(",", " ")


def _amounts_differ(a: float, b: float) -> bool:
    return abs(a - b) > _AMOUNT_TOLERANCE


def validate_amounts(invoice_data: InvoiceData, raw_text: str) -> list[ValidationIssue]:
    """
    Szabályalapú összeg-ellenőrzés – kiegészíti a Gemini validációt.
    A PDF/OCR szövegből kiolvasott összesítő sorok is számítanak.
    """
    if not raw_text:
        return []

    issues: list[ValidationIssue] = []
    text = raw_text

    net_text = _extract_labeled_amount(text, _LABEL_PATTERNS["net"])
    vat_text = _extract_labeled_amount(text, _LABEL_PATTERNS["vat"])
    gross_text = _extract_labeled_amount(text, _LABEL_PATTERNS["gross"])
    due_text = _extract_labeled_amount(text, _LABEL_PATTERNS["amount_due"])

    net = net_text if net_text is not None else invoice_data.net_amount
    vat = vat_text if vat_text is not None else invoice_data.vat_amount
    gross = gross_text if gross_text is not None else invoice_data.gross_amount

    # Nettó + ÁFA ≈ bruttó
    if net is not None and vat is not None and gross is not None:
        if _amounts_differ(net + vat, gross):
            issues.append(
                ValidationIssue(
                    field="gross_amount",
                    severity=InvoiceStatus.WARNING,
                    message=(
                        f"Az összegek nem egyeznek: nettó ({_fmt_ft(net)}) + ÁFA ({_fmt_ft(vat)}) "
                        f"≠ bruttó ({_fmt_ft(gross)})."
                    ),
                    suggestion="Ellenőrizze a nettó, ÁFA és bruttó összesítő sorokat.",
                )
            )

    # Bruttó vs fizetendő – a demo számlák szándékos hibája
    gross_for_due = gross_text if gross_text is not None else invoice_data.gross_amount
    if gross_for_due is not None and due_text is not None:
        if _amounts_differ(gross_for_due, due_text):
            issues.append(
                ValidationIssue(
                    field="gross_amount",
                    severity=InvoiceStatus.WARNING,
                    message=(
                        f"A fizetendő összeg ({_fmt_ft(due_text)} Ft) eltér a bruttó összegtől "
                        f"({_fmt_ft(gross_for_due)} Ft)."
                    ),
                    suggestion="A számlán a fizetendő mező nem egyezik a bruttó végösszeggel – javítás szükséges.",
                )
            )

    return issues
