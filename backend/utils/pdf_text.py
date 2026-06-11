# PDF szöveg kinyerés – Document AI fallback (Gemini tovább dolgozik a nyers szöveggel)
from pathlib import Path

from pypdf import PdfReader

from utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """Beágyazott PDF szöveg kinyerése (OCR nélkül – ReportLab mintákhoz elegendő)."""
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        return ""

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)

    combined = "\n".join(parts).strip()
    logger.info(f"PDF szöveg kinyerve: {path.name} ({len(combined)} karakter)")
    return combined
