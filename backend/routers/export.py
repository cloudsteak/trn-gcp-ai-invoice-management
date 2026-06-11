# Export végpontok – PDF, XLSX, CSV és könyvelői adatlap letöltése
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.result import InvoiceResult
from services.exporter import (
    generate_pdf,
    generate_xlsx,
    generate_csv,
    generate_xlsx_accounting,
)
from routers.process import _jobs as jobs
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ExportRequest(BaseModel):
    """Export kérés – job_id vagy közvetlen eredménylista (frontend fájlonkénti feldolgozás)."""
    job_id: Optional[str] = None
    file_ids: Optional[List[str]] = None
    results: Optional[List[InvoiceResult]] = None


def get_results_for_export(
    job_id: Optional[str],
    file_ids: Optional[List[str]],
    direct_results: Optional[List[InvoiceResult]] = None,
):
    """Eredmények job-ból vagy közvetlenül a kérés body-ból."""
    if direct_results is not None:
        results = direct_results
    else:
        if not job_id or job_id not in jobs:
            raise HTTPException(status_code=404, detail="A megadott job nem található.")
        job = jobs[job_id]
        if job["status"] != "done":
            raise HTTPException(status_code=400, detail="A feldolgozás még nem fejeződött be.")
        results = job.get("results", [])

    if file_ids:
        results = [r for r in results if r.file_id in file_ids]

    if not results:
        raise HTTPException(status_code=400, detail="Nincs exportálható eredmény.")

    return results


@router.post("/export/pdf")
async def export_pdf(request: ExportRequest):
    """Feldolgozási eredmények exportálása PDF formátumban."""
    results = get_results_for_export(request.job_id, request.file_ids, request.results)
    pdf_bytes = generate_pdf(results)

    logger.info(f"PDF export generálva: {len(results)} számla")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=szamlak_riport.pdf"},
    )


@router.post("/export/xlsx")
async def export_xlsx(request: ExportRequest):
    """Feldolgozási eredmények exportálása általános XLSX formátumban."""
    results = get_results_for_export(request.job_id, request.file_ids, request.results)
    xlsx_bytes = generate_xlsx(results)

    logger.info(f"XLSX export generálva: {len(results)} számla")
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=szamlak.xlsx"},
    )


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Feldolgozási eredmények exportálása CSV formátumban (UTF-8 BOM, Excel kompatibilis)."""
    results = get_results_for_export(request.job_id, request.file_ids, request.results)
    csv_bytes = generate_csv(results)

    logger.info(f"CSV export generálva: {len(results)} számla")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=szamlak.csv"},
    )


@router.post("/export/xlsx-accounting")
async def export_xlsx_accounting(request: ExportRequest):
    """
    Könyvelői adatlap exportálása – rögzített oszlopszerkezetű XLSX.
    Fájlnév formátum: szamlak_konyvelo_YYYYMMDD.xlsx
    """
    results = get_results_for_export(request.job_id, request.file_ids, request.results)
    xlsx_bytes = generate_xlsx_accounting(results)

    # Dátum alapú fájlnév generálása
    today = date.today().strftime("%Y%m%d")
    filename = f"szamlak_konyvelo_{today}.xlsx"

    logger.info(f"Könyvelői XLSX export generálva: {len(results)} számla")
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
