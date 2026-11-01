# Google Cloud Document AI Invoice Parser integráció – számla adatok kinyerése
import asyncio
import time
from datetime import date, datetime
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import InternalServerError, ResourceExhausted, ServiceUnavailable
from google.cloud import documentai_v1 as documentai

from config import settings
from models.invoice import InvoiceData, InvoiceLineItem
from utils.api_trace import annotate_last_trace, clip_text, record_api_call  # CSAK AZ API-NÉZET MIATT
from utils.logger import get_logger

logger = get_logger(__name__)

_client: Optional[tuple[str, documentai.DocumentProcessorServiceClient]] = None

_DOCAI_ENDPOINTS = {
    "eu": "eu-documentai.googleapis.com",
    "us": "us-documentai.googleapis.com",
}

_RETRIABLE_DOCAI_ERRORS = (InternalServerError, ServiceUnavailable, ResourceExhausted)

# Globális zár – csak a tényleges API hívás idejére (retry várakozás közben szabad)
_docai_lock = asyncio.Lock()
_docai_last_finished: float = 0.0

_DATE_FORMATS = ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y")

_ENTITY_ALIASES = {
    "invoice_number": ("invoice_id", "invoice_number"),
    "invoice_date": ("invoice_date",),
    "due_date": ("due_date", "payment_due_date"),
    "completion_date": ("delivery_date", "service_date", "ship_date"),
    "supplier_tax_id": ("supplier_tax_id", "supplier_vat_id", "supplier_registration"),
    "buyer_tax_id": ("receiver_tax_id", "receiver_vat_id", "receiver_registration"),
    "net_amount": ("net_amount",),
    "vat_amount": ("vat_tax_amount", "total_tax_amount", "tax_amount"),
    "gross_amount": ("total_amount", "amount_due"),
    "currency": ("currency",),
    "supplier_name": ("supplier_name",),
    "supplier_address": ("supplier_address",),
    "buyer_name": ("receiver_name", "customer_name"),
    "buyer_address": ("receiver_address", "customer_address"),
}


def get_client() -> documentai.DocumentProcessorServiceClient:
    """Document AI kliens – a GCP_LOCATION-nek megfelelő regionális endpointtal."""
    global _client
    location = settings.gcp_location.lower()
    if _client is None or _client[0] != location:
        endpoint = _DOCAI_ENDPOINTS.get(location)
        client_options = ClientOptions(api_endpoint=endpoint) if endpoint else None
        client = documentai.DocumentProcessorServiceClient(client_options=client_options)
        _client = (location, client)
    return _client[1]


def get_processor_name() -> str:
    """Teljes processor erőforrás név összeállítása a konfigurációból."""
    return (
        f"projects/{settings.gcp_project_id}"
        f"/locations/{settings.gcp_location}"
        f"/processors/{settings.gcp_processor_id}"
    )


def _get_entity_value(entities: list, entity_type: str) -> Optional[str]:
    """Adott típusú entitás szöveges értékének kinyerése."""
    for entity in entities:
        if entity.type_ == entity_type:
            return entity.mention_text
    return None


def _get_entity_by_aliases(entities: list, *aliases: str) -> Optional[str]:
    """Entitás keresése alias nevek listájával."""
    for alias in aliases:
        value = _get_entity_value(entities, alias)
        if value and value.strip():
            return value.strip()
    return None


def _parse_entity_date(entities: list, *aliases: str) -> Optional[date]:
    """Dátum entitás – normalizált érték vagy szöveg alapján."""
    for entity in entities:
        if entity.type_ not in aliases:
            continue
        normalized = entity.normalized_value
        if normalized and normalized.date_value.year:
            dv = normalized.date_value
            return date(dv.year, dv.month or 1, dv.day or 1)
        if entity.mention_text:
            text = entity.mention_text.strip()
            for fmt in _DATE_FORMATS:
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
    return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Szöveges számérték float-tá alakítása (pl. '38 000 Ft' → 38000)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = value.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
        digits = "".join(c if c.isdigit() or c in ".-" else " " for c in cleaned)
        number = digits.split()[0] if digits.split() else cleaned
        return float(number)
    except (ValueError, IndexError, AttributeError):
        return None


def _parse_line_items(document: documentai.Document) -> list:
    """Tételsorok kinyerése a Document AI válaszból."""
    line_items = []
    for entity in document.entities:
        if entity.type_ == "line_item":
            item = InvoiceLineItem()
            for prop in entity.properties:
                if prop.type_ == "line_item/description":
                    item.description = prop.mention_text
                elif prop.type_ == "line_item/quantity":
                    item.quantity = _parse_float(prop.mention_text)
                elif prop.type_ == "line_item/unit_price":
                    item.unit_price = _parse_float(prop.mention_text)
                elif prop.type_ == "line_item/amount":
                    item.total = _parse_float(prop.mention_text)
            line_items.append(item)
    return line_items


def _mime_type_for_path(file_path: str, file_name: str) -> str:
    """MIME type a fájl kiterjesztéséből – előnyben a tényleges elérési út."""
    for name in (file_path, file_name):
        if "." in name:
            ext = name.rsplit(".", 1)[-1].lower()
            if ext == "pdf":
                return "application/pdf"
            if ext in ("jpg", "jpeg"):
                return "image/jpeg"
            if ext == "png":
                return "image/png"
    return "application/octet-stream"


# --- CSAK AZ API-NÉZET MIATT ---
# A processDocument hívás olvasható másolata. A Document AI kérést nem módosítja.
def _docai_request_summary(file_name: str, mime_type: str, file_size: int, attempt: int) -> dict:
    """A processDocument hívás oktatási másolata – bináris tartalom nélkül."""
    location = settings.gcp_location.lower()
    host = _DOCAI_ENDPOINTS.get(location, "documentai.googleapis.com")
    processor = get_processor_name()
    return {
        "method": "POST",
        "endpoint": f"https://{host}/v1/{processor}:process",
        "processor": processor,
        "mime_type": mime_type,
        "file_name": file_name,
        "file_size_bytes": file_size,
        "raw_document": "(bináris fájltartalom, nincs megjelenítve)",
        "attempt": attempt,
    }


def _entity_brief(entity) -> dict:
    """Egy Document AI entitás rövid, JSON-barát kivonata."""
    item = {
        "type": entity.type_,
        "mention_text": clip_text(entity.mention_text, 200),
        "confidence": round(float(entity.confidence), 3) if entity.confidence else None,
    }
    properties = list(entity.properties or [])
    if properties:
        item["properties"] = [
            {
                "type": prop.type_,
                "mention_text": clip_text(prop.mention_text, 120),
            }
            for prop in properties[:12]
        ]
    return item


def _docai_response_summary(document: documentai.Document) -> dict:
    """A Document AI válasz oktatási kivonata: OCR részlet és entitások."""
    entities = list(document.entities)
    text = document.text or ""
    shown = [_entity_brief(entity) for entity in entities[:40]]
    return {
        "note": (
            "Invoice Parser kimenet. A mezőfelismerés tévedhet; "
            "a könyvelői szöveg külön, az AI model hívásban van."
        ),
        "text_length": len(text),
        "text_excerpt": clip_text(text, 2500),
        "page_count": len(document.pages),
        "entity_count": len(entities),
        "entities": shown,
        "entities_truncated": len(entities) > 40,
    }


# --- API-NÉZET VÉGE ---


async def _call_process_document_with_retry(
    client: documentai.DocumentProcessorServiceClient,
    request: documentai.ProcessRequest,
    file_name: str,
    mime_type: str,  # CSAK AZ API-NÉZET MIATT
    file_size: int,  # CSAK AZ API-NÉZET MIATT
):
    """
    Document AI hívás újrapróbálással.
    A várakozás a zár NÉLKÜL történik – más kérések nem blokkolódnak 30 mp-re.
    """
    global _docai_last_finished

    max_retries = settings.docai_max_retries
    base_delay = settings.docai_retry_base_seconds
    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 1):
        min_gap = settings.batch_file_delay_seconds
        if _docai_last_finished > 0 and min_gap > 0:
            elapsed = time.monotonic() - _docai_last_finished
            if elapsed < min_gap:
                wait = min_gap - elapsed
                logger.info(f"Document AI cooldown: {wait:.1f}s várakozás ({file_name})")
                await asyncio.sleep(wait)

        async with _docai_lock:
            started = time.perf_counter()
            try:
                response = await asyncio.to_thread(
                    client.process_document,
                    request=request,
                )
                _docai_last_finished = time.monotonic()
                # CSAK AZ API-NÉZET MIATT – a válasz feldolgozása ez alatt, a return-nél folytatódik
                try:
                    response_summary = _docai_response_summary(response.document)
                except Exception as summary_exc:
                    logger.warning(f"Document AI válasz kivonata nem készült el: {summary_exc}")
                    response_summary = {"note": "A válasz megérkezett, a kivonat nem készült el."}
                record_api_call(
                    service="Document AI",
                    operation="processDocument",
                    status="ok",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    request=_docai_request_summary(file_name, mime_type, file_size, attempt),
                    response=response_summary,
                )
                return response
            except _RETRIABLE_DOCAI_ERRORS as exc:
                last_error = exc
                _docai_last_finished = time.monotonic()
                # CSAK AZ API-NÉZET MIATT
                record_api_call(
                    service="Document AI",
                    operation="processDocument",
                    status="error",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    request=_docai_request_summary(file_name, mime_type, file_size, attempt),
                    error=str(exc),
                )
                if attempt >= max_retries:
                    break
            except Exception as exc:
                _docai_last_finished = time.monotonic()
                # CSAK AZ API-NÉZET MIATT
                record_api_call(
                    service="Document AI",
                    operation="processDocument",
                    status="error",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    request=_docai_request_summary(file_name, mime_type, file_size, attempt),
                    error=str(exc),
                )
                raise

        wait_seconds = min(base_delay * (2 ** (attempt - 1)), 16)
        logger.warning(
            f"Document AI átmeneti hiba ({file_name}), "
            f"újrapróba {attempt}/{max_retries} {wait_seconds}s múlva: {last_error}"
        )
        await asyncio.sleep(wait_seconds)

    raise last_error


async def process_document(file_path: str, file_name: str) -> tuple[InvoiceData, str]:
    """
    Egy számla fájl feldolgozása a Document AI Invoice Parser segítségével.

    Returns:
        (InvoiceData, raw_text): Kinyert adatok és a teljes OCR szöveg (Gemini-nek).
    """
    mime_type = _mime_type_for_path(file_path, file_name)

    with open(file_path, "rb") as f:
        file_content = f.read()

    raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
    request = documentai.ProcessRequest(
        name=get_processor_name(),
        raw_document=raw_document,
    )

    logger.info(f"Document AI feldolgozás elindítva: {file_name}")
    client = get_client()
    response = await _call_process_document_with_retry(
        client,
        request,
        file_name,
        mime_type,  # CSAK AZ API-NÉZET MIATT
        len(file_content),  # CSAK AZ API-NÉZET MIATT
    )

    document = response.document
    entities = document.entities
    raw_text = document.text or ""

    confidences = [e.confidence for e in entities if e.confidence > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    invoice_data = InvoiceData(
        invoice_number=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["invoice_number"]),
        invoice_date=_parse_entity_date(entities, *_ENTITY_ALIASES["invoice_date"]),
        due_date=_parse_entity_date(entities, *_ENTITY_ALIASES["due_date"]),
        completion_date=_parse_entity_date(entities, *_ENTITY_ALIASES["completion_date"]),
        supplier_name=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["supplier_name"]),
        supplier_address=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["supplier_address"]),
        supplier_tax_id=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["supplier_tax_id"]),
        buyer_name=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["buyer_name"]),
        buyer_address=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["buyer_address"]),
        buyer_tax_id=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["buyer_tax_id"]),
        net_amount=_parse_float(_get_entity_by_aliases(entities, *_ENTITY_ALIASES["net_amount"])),
        vat_amount=_parse_float(_get_entity_by_aliases(entities, *_ENTITY_ALIASES["vat_amount"])),
        gross_amount=_parse_float(_get_entity_by_aliases(entities, *_ENTITY_ALIASES["gross_amount"])),
        currency=_get_entity_by_aliases(entities, *_ENTITY_ALIASES["currency"]),
        line_items=_parse_line_items(document),
        confidence_score=avg_confidence,
    )

    if avg_confidence is not None and avg_confidence < 0.7:
        logger.warning(f"Alacsony konfidencia ({avg_confidence:.2f}): {file_name}")

    # CSAK AZ API-NÉZET MIATT – a parserből kiolvasott mezők a DOCAI kártyán
    annotate_last_trace("Document AI", {
        "parsed_invoice": invoice_data.model_dump(mode="json"),
    })

    logger.info(f"Document AI feldolgozás kész: {file_name}")
    return invoice_data, raw_text
