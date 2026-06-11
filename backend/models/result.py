# Feldolgozási eredmény modellek – státusz és validációs hibák kezelése
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from models.invoice import InvoiceData


class InvoiceStatus(str, Enum):
    """Számla feldolgozási státusza"""
    OK = "ok"               # Minden rendben
    WARNING = "warning"     # Figyelmeztetés (nem blokkoló)
    ERROR = "error"         # Hiba (pl. hiányzó adószám)


class ValidationIssue(BaseModel):
    """Egyetlen validációs probléma leírása"""
    field: Optional[str] = None            # Érintett mező neve
    severity: InvoiceStatus                # ok / warning / error
    message: str                           # Magyar nyelvű hibaüzenet
    suggestion: Optional[str] = None       # Javítási javaslat


class InvoiceResult(BaseModel):
    """Egy számla teljes feldolgozási eredménye"""
    file_name: str
    file_id: str                                    # UUID alapú belső azonosító
    status: InvoiceStatus
    invoice_data: Optional[InvoiceData] = None
    issues: List[ValidationIssue] = []
    gemini_summary: Optional[str] = None            # Gemini könyvelői értékelés szövege
    processing_time_ms: Optional[int] = None        # Feldolgozási idő milliszekundumban
