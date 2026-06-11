# Orchestrátor – Document AI és Gemini szolgáltatások összefűzése
import time
from datetime import date, datetime
from pathlib import Path

from pydantic import ValidationError

from google.api_core.exceptions import GoogleAPIError

from config import settings
from models.invoice import InvoiceData
from models.result import InvoiceResult, InvoiceStatus, ValidationIssue
from services.document_ai import process_document
from services.gemini import validate_invoice
from utils.amount_validation import validate_amounts
from utils.file_handler import get_original_filename, resolve_upload_file_path
from utils.logger import get_logger
from utils.pdf_text import extract_text_from_pdf

logger = get_logger(__name__)

# Document AI hibák, ahol PDF-ből Gemini fallback lehetséges
_DOCAI_FALLBACK_MARKERS = (
    "Internal error encountered",
    "503",
    "500",
    "ServiceUnavailable",
    "ResourceExhausted",
)

_DATE_FIELDS = frozenset({"invoice_date", "due_date", "completion_date"})
_FLOAT_FIELDS = frozenset({"net_amount", "vat_amount", "vat_rate", "gross_amount", "confidence_score"})
_MISSING_MARKERS = frozenset({
    "hiányzik", "hianyzik", "missing", "n/a", "na", "null", "none", "-", "—", "?", "unknown", "ismeretlen",
})

_DATE_FORMATS = ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y")


def _is_missing_placeholder(value) -> bool:
    """Gemini placeholder értékek – ezeket nem írjuk be a modellbe."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().lower() in _MISSING_MARKERS
    return False


def _parse_filled_date(value) -> date | None:
    """Dátum mező parse-olása – sikertelenül None (kihagyás)."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_filled_float(value) -> float | None:
    """Szám mező parse-olása – sikertelenül None (kihagyás)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        cleaned = value.replace(" ", "").replace(",", ".")
        # Nem numerikus suffix eltávolítása (pl. "Ft", "EUR")
        digits = "".join(c if c.isdigit() or c in ".-" else " " for c in cleaned)
        number = digits.split()[0] if digits.split() else cleaned
        return float(number)
    except (ValueError, IndexError):
        return None


def _coerce_filled_field(field: str, value):
    """Gemini filled_fields érték típushelyes alakítása – érvénytelen értéknél None."""
    if _is_missing_placeholder(value):
        return None
    if field in _DATE_FIELDS:
        return _parse_filled_date(value)
    if field in _FLOAT_FIELDS:
        return _parse_filled_float(value)
    if isinstance(value, str):
        return value.strip()
    return value


def _determine_final_status(issues: list[ValidationIssue]) -> InvoiceStatus:
    """
    Végső státusz meghatározása a validációs hibák alapján.
    A legrosszabb súlyosságú issue határozza meg az összesített státuszt.
    """
    if any(i.severity == InvoiceStatus.ERROR for i in issues):
        return InvoiceStatus.ERROR
    if any(i.severity == InvoiceStatus.WARNING for i in issues):
        return InvoiceStatus.WARNING
    return InvoiceStatus.OK


def _apply_filled_fields(invoice_data: InvoiceData, filled_fields: dict) -> InvoiceData:
    """
    Gemini által pótolt mezők alkalmazása az InvoiceData modellre.
    Csak érvényes, típushelyes értékeket ír be – placeholder (pl. HIÁNYZIK) kihagyva.
    """
    if not filled_fields:
        return invoice_data

    current = invoice_data.model_dump()
    updates = {}

    for field, value in filled_fields.items():
        if field not in current or current[field] is not None:
            continue
        coerced = _coerce_filled_field(field, value)
        if coerced is None:
            continue
        try:
            invoice_data.model_copy(update={field: coerced})
            updates[field] = coerced
        except ValidationError:
            logger.warning(f"Gemini filled_fields – érvénytelen érték kihagyva: {field}={value!r}")

    if not updates:
        return invoice_data

    return invoice_data.model_copy(update=updates)


def _field_is_populated(invoice_data: InvoiceData, field: str | None) -> bool:
    """Mező kitöltött-e – a hamis hiányzó issue-k kiszűréséhez."""
    if not field:
        return False
    value = invoice_data.model_dump().get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def _filter_resolved_issues(
    invoice_data: InvoiceData,
    issues: list[ValidationIssue],
) -> list[ValidationIssue]:
    """Issue-k eltávolítása, ha a mező a pótlás után már kitöltött."""
    return [
        issue
        for issue in issues
        if not _field_is_populated(invoice_data, issue.field)
    ]


def _can_gemini_pdf_fallback(file_path: str, exc: Exception, file_name: str = "") -> bool:
    """PDF esetén Document AI hiba → Gemini a beágyazott PDF szövegből kinyer."""
    is_pdf = file_path.lower().endswith(".pdf") or file_name.lower().endswith(".pdf")
    if not is_pdf:
        return False
    msg = str(exc)
    if "Invalid location" in msg or "Invalid image content" in msg:
        return False
    if isinstance(exc, GoogleAPIError):
        return True
    return any(marker in msg for marker in _DOCAI_FALLBACK_MARKERS)


async def _finalize_with_gemini(
    file_id: str,
    file_name: str,
    invoice_data: InvoiceData,
    raw_text: str,
    start_time: float,
    *,
    docai_fallback: bool = False,
) -> InvoiceResult:
    """Gemini validáció és InvoiceResult összeállítása."""
    logger.info(f"Gemini validáció: {file_name}")
    gemini_result = await validate_invoice(invoice_data, raw_text=raw_text)
    invoice_data = _apply_filled_fields(invoice_data, gemini_result.filled_fields)
    issues = _filter_resolved_issues(invoice_data, gemini_result.issues)
    issues.extend(validate_amounts(invoice_data, raw_text))

    if docai_fallback:
        logger.info(f"Document AI helyett PDF+Gemini fallback: {file_name}")

    final_status = _determine_final_status(issues)
    processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info(f"Feldolgozás kész: {file_name} ({processing_time_ms}ms, státusz: {final_status})")

    return InvoiceResult(
        file_name=file_name,
        file_id=file_id,
        status=final_status,
        invoice_data=invoice_data,
        issues=issues,
        gemini_summary=gemini_result.summary,
        processing_time_ms=processing_time_ms,
    )


async def _process_via_pdf_fallback(
    file_id: str,
    file_name: str,
    file_path: str,
    start_time: float,
) -> InvoiceResult:
    """Document AI hiba után – PDF szöveg + Gemini kinyerés."""
    raw_text = extract_text_from_pdf(file_path)
    if not raw_text.strip():
        raise ValueError("A PDF-ből nem sikerült szöveget kinyerni.")

    logger.warning(f"Document AI fallback (PDF+Gemini): {file_name}")
    return await _finalize_with_gemini(
        file_id,
        file_name,
        InvoiceData(),
        raw_text,
        start_time,
        docai_fallback=True,
    )


async def process_invoice(file_id: str, upload_dir: str) -> InvoiceResult:
    """
    Egyetlen számla teljes feldolgozása:
    1. Document AI – strukturált adatkinyerés
    2. Gemini – validáció, kiegészítés, könyvelői értékelés
    3. Eredmény összeállítása

    Args:
        file_id: A fájl UUID alapú azonosítója
        upload_dir: A feltöltési könyvtár elérési útja

    Returns:
        InvoiceResult: A teljes feldolgozási eredmény
    """
    start_time = time.time()

    # Fájl megkeresése az upload könyvtárban (meta.json kizárva)
    uploaded = resolve_upload_file_path(upload_dir, file_id)

    if uploaded is None:
        logger.error(f"Fájl nem található: {file_id}")
        return InvoiceResult(
            file_name="ismeretlen",
            file_id=file_id,
            status=InvoiceStatus.ERROR,
            issues=[ValidationIssue(
                field=None,
                severity=InvoiceStatus.ERROR,
                message="A fájl nem található a szerveren.",
            )],
        )

    file_path = str(uploaded)
    stored_name = uploaded.name
    file_name = get_original_filename(file_id, upload_dir) or stored_name

    async def _try_pdf_fallback(exc: Exception) -> InvoiceResult | None:
        if not _can_gemini_pdf_fallback(file_path, exc, file_name):
            return None
        logger.warning(f"Document AI hiba, PDF+Gemini fallback: {file_name} ({exc})")
        return await _process_via_pdf_fallback(file_id, file_name, file_path, start_time)

    try:
        # 1. lépés: Document AI – ha bukik bizonyos PDF-eken, Gemini fallback
        logger.info(f"Document AI feldolgozás: {file_name}")
        try:
            invoice_data, raw_text = await process_document(file_path, file_name)
        except Exception as docai_exc:
            fallback_result = await _try_pdf_fallback(docai_exc)
            if fallback_result is not None:
                return fallback_result
            raise

        return await _finalize_with_gemini(
            file_id, file_name, invoice_data, raw_text, start_time
        )

    except Exception as e:
        fallback_result = await _try_pdf_fallback(e)
        if fallback_result is not None:
            return fallback_result

        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Feldolgozási hiba ({file_name}): {e}")

        error_text = str(e)
        if "Invalid location" in error_text:
            suggestion = (
                f"A GCP_LOCATION ({settings.gcp_location}) nem egyezik a Document AI processzor "
                "régiójával. GCP Console → Document AI → Processors → nézd meg a régiót (us/eu), "
                "majd állítsd be a backend/.env fájlban: GCP_LOCATION=us vagy GCP_LOCATION=eu"
            )
            message = "Document AI régió eltérés – ellenőrizze a GCP_LOCATION beállítást."
        elif "Invalid image content" in error_text:
            suggestion = (
                "A képfájl formátuma nem fogadható el. Próbálja PDF-ként feltölteni, "
                "vagy JPG/PNG formátumban, max. 20 MB méretben."
            )
            message = "Érvénytelen képfájl – a Document AI nem tudta feldolgozni."
        elif "Internal error encountered" in error_text or "503" in error_text:
            suggestion = (
                "A Document AI átmeneti hiba miatt nem dolgozta fel a fájlt. "
                "Várjon pár másodpercet, majd indítsa újra a feldolgozást – batch-ben a fájlok most sorban futnak."
            )
            message = "Document AI átmeneti szolgáltatási hiba."
        else:
            suggestion = "Ellenőrizze a fájl integritását és próbálja újra."
            message = f"Feldolgozási hiba: {error_text}"

        return InvoiceResult(
            file_name=file_name,
            file_id=file_id,
            status=InvoiceStatus.ERROR,
            processing_time_ms=processing_time_ms,
            issues=[ValidationIssue(
                field="gcp_location",
                severity=InvoiceStatus.ERROR,
                message=message,
                suggestion=suggestion,
            )],
        )
