# Google Cloud Document AI Invoice Parser integráció – számla adatok kinyerése
import os
from typing import Optional

from google.cloud import documentai_v1 as documentai

from config import settings
from models.invoice import InvoiceData, InvoiceLineItem
from utils.logger import get_logger

logger = get_logger(__name__)

# Document AI kliens – újrafelhasználható példány
_client: Optional[documentai.DocumentProcessorServiceClient] = None


def get_client() -> documentai.DocumentProcessorServiceClient:
    """Document AI kliens létrehozása vagy visszaadása (singleton)."""
    global _client
    if _client is None:
        _client = documentai.DocumentProcessorServiceClient()
    return _client


def get_processor_name() -> str:
    """Teljes processor erőforrás név összeállítása a konfigurációból."""
    return (
        f"projects/{settings.gcp_project_id}"
        f"/locations/{settings.gcp_location}"
        f"/processors/{settings.gcp_processor_id}"
    )


def _get_entity_value(entities: list, entity_type: str) -> Optional[str]:
    """
    Adott típusú entitás szöveges értékének kinyerése a Document AI válaszból.
    Ha az entitás nem található, None-t ad vissza.
    """
    for entity in entities:
        if entity.type_ == entity_type:
            return entity.mention_text
    return None


def _get_entity_confidence(entities: list, entity_type: str) -> Optional[float]:
    """Adott típusú entitás konfidencia értékének kinyerése."""
    for entity in entities:
        if entity.type_ == entity_type:
            return entity.confidence
    return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Szöveges számérték float-tá alakítása, hibás értéknél None visszaadása."""
    if value is None:
        return None
    try:
        # Ezres elválasztók és szóközök eltávolítása
        cleaned = value.replace(" ", "").replace(",", ".")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_line_items(document: documentai.Document) -> list:
    """
    Tételsorok kinyerése a Document AI válaszból.
    A line_item típusú entitások gyerek entitásait dolgozza fel.
    """
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


async def process_document(file_path: str, file_name: str) -> InvoiceData:
    """
    Egy számla fájl feldolgozása a Document AI Invoice Parser segítségével.
    Visszaadja a kinyert adatokat InvoiceData modell formájában.

    Args:
        file_path: A feldolgozandó fájl teljes elérési útja
        file_name: A fájl eredeti neve (MIME type meghatározásához)

    Returns:
        InvoiceData: A számláról kinyert strukturált adatok
    """
    # Fájl beolvasása és MIME type meghatározása
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    mime_types = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    mime_type = mime_types.get(extension, "application/octet-stream")

    with open(file_path, "rb") as f:
        file_content = f.read()

    # Document AI kérés összeállítása
    raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
    request = documentai.ProcessRequest(
        name=get_processor_name(),
        raw_document=raw_document,
    )

    logger.info(f"Document AI feldolgozás elindítva: {file_name}")

    # Szinkron hívás – Document AI SDK nem async, de FastAPI threadpool-ban fut
    client = get_client()
    response = client.process_document(request=request)
    document = response.document
    entities = document.entities

    # Konfidencia számítás – az összes entitás átlaga
    confidences = [e.confidence for e in entities if e.confidence > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    # Entitások leképezése InvoiceData mezőkre
    invoice_data = InvoiceData(
        invoice_number=_get_entity_value(entities, "invoice_id"),
        supplier_name=_get_entity_value(entities, "supplier_name"),
        supplier_address=_get_entity_value(entities, "supplier_address"),
        supplier_tax_id=_get_entity_value(entities, "supplier_tax_id"),
        buyer_name=_get_entity_value(entities, "receiver_name"),
        buyer_address=_get_entity_value(entities, "receiver_address"),
        buyer_tax_id=_get_entity_value(entities, "receiver_tax_id"),
        net_amount=_parse_float(_get_entity_value(entities, "net_amount")),
        vat_amount=_parse_float(_get_entity_value(entities, "vat_tax_amount")),
        gross_amount=_parse_float(_get_entity_value(entities, "total_amount")),
        currency=_get_entity_value(entities, "currency"),
        line_items=_parse_line_items(document),
        confidence_score=avg_confidence,
    )

    # Alacsony konfidenciájú kinyerés jelzése
    if avg_confidence is not None and avg_confidence < 0.7:
        logger.warning(f"Alacsony konfidencia ({avg_confidence:.2f}): {file_name}")

    logger.info(f"Document AI feldolgozás kész: {file_name}")
    return invoice_data
