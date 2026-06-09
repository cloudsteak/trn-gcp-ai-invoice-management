# Fájlfeltöltési végpont – multipart/form-data fogadása és validálása
import uuid
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from config import settings
from utils.file_handler import validate_file, save_file
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class UploadedFile(BaseModel):
    """Egyetlen feltöltött fájl azonosítója és státusza"""
    file_id: str
    file_name: str
    status: str


class UploadResponse(BaseModel):
    """Feltöltési válasz – az összes fájl azonosítójával"""
    files: List[UploadedFile]


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Több számla fájl feltöltése egyszerre.
    Elfogadott formátumok: PDF, JPG, JPEG, PNG.
    """
    # Batch méret ellenőrzése
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=400,
            detail=f"Egyszerre maximum {settings.max_files_per_batch} fájl tölthető fel."
        )

    uploaded = []

    for file in files:
        # Fájl validálása (típus és méret alapján)
        await validate_file(file, settings)

        # Egyedi azonosító generálása és fájl mentése
        file_id = str(uuid.uuid4())
        await save_file(file, file_id, settings.upload_dir)

        logger.info(f"Fájl sikeresen feltöltve: {file.filename} (ID: {file_id})")
        uploaded.append(UploadedFile(
            file_id=file_id,
            file_name=file.filename,
            status="uploaded"
        ))

    return UploadResponse(files=uploaded)
