# Feldolgozási végpontok – batch indítás és státusz lekérdezés
import asyncio
import uuid
from typing import List, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from models.result import InvoiceResult
from services.processor import process_invoice
from utils.file_handler import cleanup_upload_dir
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# In-memory job tárolás – Cloud Run állapot nélküli, egy kérés alatt elegendő
_jobs: Dict[str, dict] = {}


class ProcessRequest(BaseModel):
    """Feldolgozási kérés – fájl azonosítók listája"""
    file_ids: List[str]


class ProcessStatusResponse(BaseModel):
    """Feldolgozási státusz válasz"""
    job_id: str
    status: str                         # processing | done | error
    progress: str                       # pl. "2/4"
    results: List[InvoiceResult] = []


async def _run_batch(job_id: str, file_ids: List[str]) -> None:
    """
    Batch feldolgozás háttérben – minden fájlt párhuzamosan dolgoz fel.
    Az eredményeket a _jobs szótárban tárolja.
    """
    _jobs[job_id]["status"] = "processing"
    total = len(file_ids)

    try:
        # Párhuzamos feldolgozás asyncio.gather-rel
        tasks = [process_invoice(file_id, settings.upload_dir) for file_id in file_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Egyedi fájl hiba nem állítja meg a többi feldolgozását
                logger.error(f"Feldolgozási hiba ({file_ids[i]}): {result}")
            else:
                processed.append(result)
                # Fájl törlése feldolgozás után
                cleanup_upload_dir(settings.upload_dir, file_ids[i])

            _jobs[job_id]["progress"] = f"{i + 1}/{total}"

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["results"] = processed

    except Exception as e:
        logger.error(f"Batch feldolgozási hiba (job: {job_id}): {e}")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)


@router.post("/process")
async def start_processing(request: ProcessRequest) -> dict:
    """
    Batch feldolgozás indítása a feltöltött fájlokon.
    Azonnal visszaadja a job_id-t, a feldolgozás háttérben fut.
    """
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="Legalább egy fájl azonosítót meg kell adni.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "processing",
        "progress": f"0/{len(request.file_ids)}",
        "results": [],
    }

    # Háttérfeladat indítása – nem blokkolja a válasz visszaküldését
    asyncio.create_task(_run_batch(job_id, request.file_ids))

    logger.info(f"Batch feldolgozás elindítva: {job_id} ({len(request.file_ids)} fájl)")
    return {"job_id": job_id}


@router.get("/process/{job_id}", response_model=ProcessStatusResponse)
async def get_processing_status(job_id: str) -> ProcessStatusResponse:
    """
    Feldolgozási job aktuális státuszának lekérdezése.
    A frontend 2 másodpercenként kérdezi le, amíg status != 'done'.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job nem található: {job_id}")

    job = _jobs[job_id]
    return ProcessStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        results=job.get("results", []),
    )
