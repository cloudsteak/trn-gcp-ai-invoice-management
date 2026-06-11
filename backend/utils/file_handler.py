# Fájlkezelési segédfüggvények – validáció, mentés és törlés
import json
import os
import mimetypes
from pathlib import Path

import aiofiles
from fastapi import UploadFile, HTTPException

from utils.logger import get_logger

logger = get_logger(__name__)

# Engedélyezett MIME típusok (kiterjesztés alapú ellenőrzés kiegészítéseként)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


async def validate_file(file: UploadFile, settings) -> None:
    """
    Fájl validálása típus és méret alapján.
    HTTPException-t dob érvénytelen fájl esetén.

    Args:
        file: A feltöltött fájl
        settings: Alkalmazás konfiguráció (max méret, engedélyezett kiterjesztések)
    """
    # Kiterjesztés ellenőrzése
    extension = ""
    if file.filename and "." in file.filename:
        extension = file.filename.rsplit(".", 1)[-1].lower()

    allowed = settings.get_allowed_extensions()
    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Nem engedélyezett fájltípus: .{extension}. "
                   f"Engedélyezettek: {', '.join(allowed)}",
        )

    # MIME type ellenőrzése (kiterjesztés alapú fallback)
    content_type = file.content_type or ""
    guessed_type, _ = mimetypes.guess_type(file.filename or "")

    if content_type not in ALLOWED_MIME_TYPES and guessed_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Gyanús MIME type: {content_type} ({file.filename})")

    # Fájlméret ellenőrzése – a tartalmat beolvassuk, majd visszaállítjuk
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)

    if file_size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"A fájl mérete ({file_size_mb:.1f} MB) meghaladja a "
                   f"maximális méretet ({settings.max_file_size_mb} MB).",
        )

    # Fájl pozíció visszaállítása az olvasás után
    await file.seek(0)


async def save_file(file: UploadFile, file_id: str, upload_dir: str) -> str:
    """
    Fájl mentése az upload könyvtárba UUID alapú névvel.
    A könyvtárat létrehozza, ha nem létezik.

    Args:
        file: A feltöltött fájl
        file_id: Az egyedi fájlazonosító (UUID)
        upload_dir: A célkönyvtár elérési útja

    Returns:
        str: A mentett fájl teljes elérési útja
    """
    # Upload könyvtár létrehozása, ha nem létezik
    Path(upload_dir).mkdir(parents=True, exist_ok=True)

    # Kiterjesztés megőrzése az eredeti fájlnévből
    extension = ""
    if file.filename and "." in file.filename:
        extension = "." + file.filename.rsplit(".", 1)[-1].lower()

    file_path = os.path.join(upload_dir, f"{file_id}{extension}")

    # Aszinkron fájlírás
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Eredeti fájlnév mentése – a feldolgozási eredmény megjelenítéséhez
    if file.filename:
        meta_path = os.path.join(upload_dir, f"{file_id}.meta.json")
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as meta_file:
            await meta_file.write(json.dumps({"original_filename": file.filename}))

    logger.info(f"Fájl mentve: {file_path} ({len(content)} byte)")
    return file_path


def resolve_upload_file_path(upload_dir: str, file_id: str) -> Path | None:
    """
    A feltöltött számla fájl elérési útja.
    A {file_id}.meta.json meta fájl kizárva – a glob egyébként azt is visszaadhatja.
    """
    upload_path = Path(upload_dir)
    candidates = sorted(
        p for p in upload_path.glob(f"{file_id}.*")
        if p.name != f"{file_id}.meta.json"
    )
    return candidates[0] if candidates else None


def get_original_filename(file_id: str, upload_dir: str) -> str | None:
    """Feltöltéskor elmentett eredeti fájlnév lekérése."""
    meta_path = Path(upload_dir) / f"{file_id}.meta.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        name = data.get("original_filename")
        return name if name else None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Meta fájl olvasási hiba ({file_id}): {e}")
        return None


def delete_file(file_path: str) -> bool:
    """
    Fájl törlése a megadott elérési útról.
    Feldolgozás után hívandó a tárhely felszabadításához.

    Args:
        file_path: A törlendő fájl elérési útja

    Returns:
        bool: True ha sikerült, False ha a fájl nem létezett
    """
    try:
        os.remove(file_path)
        logger.info(f"Fájl törölve: {file_path}")
        return True
    except FileNotFoundError:
        logger.warning(f"Törlendő fájl nem található: {file_path}")
        return False
    except OSError as e:
        logger.error(f"Fájl törlési hiba ({file_path}): {e}")
        return False


def cleanup_upload_dir(upload_dir: str, file_id: str) -> None:
    """
    Adott fájl ID-hoz tartozó összes fájl törlése az upload könyvtárból.

    Args:
        upload_dir: Az upload könyvtár elérési útja
        file_id: A törlendő fájl azonosítója
    """
    upload_path = Path(upload_dir)
    for file_path in upload_path.glob(f"{file_id}.*"):
        delete_file(str(file_path))
    meta_path = upload_path / f"{file_id}.meta.json"
    if meta_path.exists():
        delete_file(str(meta_path))
