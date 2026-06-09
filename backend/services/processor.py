# Orchestrátor – Document AI és Gemini szolgáltatások összefűzése
import os
import time
from pathlib import Path

from models.invoice import InvoiceData
from models.result import InvoiceResult, InvoiceStatus, ValidationIssue
from services.document_ai import process_document
from services.gemini import validate_invoice
from utils.logger import get_logger

logger = get_logger(__name__)


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
    Csak azokat a mezőket frissíti, amelyek eredetileg None értékűek voltak.
    """
    data_dict = invoice_data.model_dump()
    for field, value in filled_fields.items():
        if field in data_dict and data_dict[field] is None and value:
            data_dict[field] = value
    return InvoiceData(**data_dict)


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

    # Fájl megkeresése az upload könyvtárban
    upload_path = Path(upload_dir)
    matching_files = list(upload_path.glob(f"{file_id}.*"))

    if not matching_files:
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

    file_path = str(matching_files[0])
    file_name = matching_files[0].name

    try:
        # 1. lépés: Document AI feldolgozás
        logger.info(f"Document AI feldolgozás: {file_name}")
        invoice_data = await process_document(file_path, file_name)

        # 2. lépés: Gemini validáció és kiegészítés
        logger.info(f"Gemini validáció: {file_name}")
        gemini_result = await validate_invoice(invoice_data)

        # 3. lépés: Gemini által pótolt mezők alkalmazása
        invoice_data = _apply_filled_fields(invoice_data, gemini_result.filled_fields)

        # 4. lépés: Végső státusz meghatározása
        final_status = _determine_final_status(gemini_result.issues)

        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Feldolgozás kész: {file_name} ({processing_time_ms}ms, státusz: {final_status})")

        return InvoiceResult(
            file_name=file_name,
            file_id=file_id,
            status=final_status,
            invoice_data=invoice_data,
            issues=gemini_result.issues,
            gemini_summary=gemini_result.summary,
            processing_time_ms=processing_time_ms,
        )

    except Exception as e:
        # Váratlan hiba esetén hibás eredmény visszaadása
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Feldolgozási hiba ({file_name}): {e}")

        return InvoiceResult(
            file_name=file_name,
            file_id=file_id,
            status=InvoiceStatus.ERROR,
            processing_time_ms=processing_time_ms,
            issues=[ValidationIssue(
                field=None,
                severity=InvoiceStatus.ERROR,
                message=f"Feldolgozási hiba: {str(e)}",
                suggestion="Ellenőrizze a fájl integritását és próbálja újra.",
            )],
        )
