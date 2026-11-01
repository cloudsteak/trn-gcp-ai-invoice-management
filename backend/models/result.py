# Feldolgozási eredmény modellek – státusz és validációs hibák kezelése
# CSAK AZ API-NÉZET MIATT: a Field és az Any import az ApiCallTrace modellhez kell
from pydantic import BaseModel, Field
from typing import Any, Optional, List
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


# CSAK AZ API-NÉZET MIATT – a számla eredményéhez nem kell, a panel olvassa
class ApiCallTrace(BaseModel):
    """Egy kimenő AI hívás oktatási nyoma. layer: docai vagy ai."""
    direction: str = "be-ai"
    layer: str = "ai"
    service: str
    operation: str
    status: str
    duration_ms: int = 0
    occurred_at: str
    request: dict[str, Any] = Field(default_factory=dict)
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class InvoiceResult(BaseModel):
    """Egy számla teljes feldolgozási eredménye"""
    file_name: str
    file_id: str                                    # UUID alapú belső azonosító
    status: InvoiceStatus
    invoice_data: Optional[InvoiceData] = None
    issues: List[ValidationIssue] = []
    gemini_summary: Optional[str] = None            # Gemini könyvelői értékelés szövege
    processing_time_ms: Optional[int] = None        # Feldolgozási idő milliszekundumban
    api_calls: List[ApiCallTrace] = []              # CSAK AZ API-NÉZET MIATT
