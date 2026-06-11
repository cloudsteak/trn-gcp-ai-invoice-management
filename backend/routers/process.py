# Feldolgozási végpontok – batch indítás és státusz lekérdezés
import asyncio
import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from models.result import InvoiceResult, InvoiceStatus
from services.processor import process_invoice
from utils.file_handler import cleanup_upload_dir
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

_jobs: Dict[str, dict] = {}


class ProcessRequest(BaseModel):
    file_ids: List[str]


class ProcessStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: str
    results: List[InvoiceResult] = []


async def _process_one(file_id: str) -> InvoiceResult:
    result = await process_invoice(file_id, settings.upload_dir)
    if result.status != InvoiceStatus.ERROR:
        cleanup_upload_dir(settings.upload_dir, file_id)
    return result


async def _run_batch(job_id: str, file_ids: List[str]) -> None:
    """Fájlonként sorban – a frontend egyesével indítja, dupla backend retry nincs."""
    _jobs[job_id]["status"] = "processing"
    total = len(file_ids)
    results: List[InvoiceResult] = []

    try:
        for i, file_id in enumerate(file_ids):
            try:
                results.append(await _process_one(file_id))
            except Exception as exc:
                logger.error(f"Váratlan feldolgozási hiba ({file_id}): {exc}")

            _jobs[job_id]["progress"] = f"{i + 1}/{total}"
            _jobs[job_id]["results"] = list(results)

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["results"] = results

    except Exception as e:
        logger.error(f"Batch feldolgozási hiba (job: {job_id}): {e}")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)


@router.post("/process")
async def start_processing(request: ProcessRequest) -> dict:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="Legalább egy fájl azonosítót meg kell adni.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "processing",
        "progress": f"0/{len(request.file_ids)}",
        "results": [],
    }

    asyncio.create_task(_run_batch(job_id, request.file_ids))

    logger.info(f"Feldolgozás elindítva: {job_id} ({len(request.file_ids)} fájl)")
    return {"job_id": job_id}


@router.get("/process/{job_id}", response_model=ProcessStatusResponse)
async def get_processing_status(job_id: str) -> ProcessStatusResponse:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job nem található: {job_id}")

    job = _jobs[job_id]
    return ProcessStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        results=job.get("results", []),
    )
