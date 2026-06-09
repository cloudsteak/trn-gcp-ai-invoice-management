# Feldolgozási végpontok – batch indítás és státusz lekérdezés
import asyncio
import uuid
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from models.result import InvoiceResult
from services.processor import process_invoice
from config import settings
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Memóriában tárolt job állapotok (production-ban Redis vagy DB kellene)
jobs: Dict[str, dict] = {}


class ProcessRequest(BaseModel):
    """Feldolgozási kérés – fájl ID-k listájával"""
    file_ids: List[str]


class ProcessResponse(BaseModel):
    """Feldolgozási válasz – job azonosítóval"""
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Job státusz lekérdezési válasz"""
    status: str                         # processing | done | error
    results: List[InvoiceResult] = []
    progress: str = "0/0"              # pl. "2/4"


async def run_batch_processing(job_id: str, file_ids: List[str]):
    """
    Háttérben futó batch feldolgozás – az összes fájlt párhuzamosan dolgozza fel.
    Az eredményeket a jobs szótárban tárolja.
    """
    total = len(file_ids)
    jobs[job_id]["total"] = total
    jobs[job_id]["completed"] = 0

    # Párhuzamos feldolgozás asyncio.gather segítségével
    tasks = [
        process_invoice(
            file_id=fid,
            upload_dir=settings.upload_dir
        )
        for fid in file_ids
    ]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Eredmények összegyűjtése, hibák kezelése
        processed = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feldolgozási hiba: {result}")
            else:
                processed.append(result)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["results"] = processed
        jobs[job_id]["completed"] = total
    except Exception as e:
        logger.error(f"Batch feldolgozási hiba (job: {job_id}): {e}")
        jobs[job_id]["status"] = "error"


@router.post("/process", response_model=ProcessResponse)
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Batch feldolgozás indítása a megadott fájl ID-kra."""
    job_id = str(uuid.uuid4())

    # Job állapot inicializálása
    jobs[job_id] = {
        "status": "processing",
        "results": [],
        "total": len(request.file_ids),
        "completed": 0,
    }

    # Feldolgozás háttérben indítása
    background_tasks.add_task(run_batch_processing, job_id, request.file_ids)
    logger.info(f"Batch feldolgozás elindítva: {job_id} ({len(request.file_ids)} fájl)")

    return ProcessResponse(job_id=job_id, status="processing")


@router.get("/process/{job_id}", response_model=JobStatusResponse)
async def get_processing_status(job_id: str):
    """Feldolgozási job aktuális állapotának lekérdezése."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="A megadott job nem található.")

    job = jobs[job_id]
    completed = job.get("completed", 0)
    total = job.get("total", 0)

    return JobStatusResponse(
        status=job["status"],
        results=job.get("results", []),
        progress=f"{completed}/{total}",
    )
