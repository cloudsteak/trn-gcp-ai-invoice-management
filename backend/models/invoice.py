# Számla adatmodellek – Pydantic alapú, Document AI kimenetének fogadásához
from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class InvoiceLineItem(BaseModel):
    """Egy tételsor a számlán"""
    description: Optional[str] = None      # Tétel leírása
    quantity: Optional[float] = None       # Mennyiség
    unit_price: Optional[float] = None     # Egységár
    total: Optional[float] = None          # Tétel összesen


class InvoiceData(BaseModel):
    """A számla összes kinyert adata"""

    # Számla azonosítók
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None         # Kelt
    due_date: Optional[date] = None             # Fizetési határidő
    completion_date: Optional[date] = None      # Teljesítés dátuma

    # Eladó / szállító adatok
    supplier_name: Optional[str] = None         # Eladó neve
    supplier_address: Optional[str] = None      # Eladó címe
    supplier_tax_id: Optional[str] = None       # Eladó adószáma – hiánya HIBA

    # Vevő adatok
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_tax_id: Optional[str] = None

    # Pénzügyi összegek
    net_amount: Optional[float] = None          # Nettó összeg
    vat_amount: Optional[float] = None          # ÁFA összeg
    vat_rate: Optional[float] = None            # ÁFA kulcs (pl. 0.27 = 27%)
    gross_amount: Optional[float] = None        # Bruttó összeg
    currency: Optional[str] = None             # Pénznem (HUF, EUR, stb.)

    # Tételsorok listája
    line_items: List[InvoiceLineItem] = []

    # Metaadatok
    language: Optional[str] = None             # Számla nyelve: "hu" vagy "en"
    confidence_score: Optional[float] = None   # Document AI konfidencia pont
