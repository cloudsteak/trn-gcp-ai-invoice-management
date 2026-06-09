# Gemini API integráció – számlaadat validáció, kiegészítés és könyvelői értékelés
import json
from typing import Optional

import google.generativeai as genai

from config import settings
from models.invoice import InvoiceData
from models.result import ValidationIssue, InvoiceStatus
from utils.logger import get_logger

logger = get_logger(__name__)

# Gemini system prompt – tapasztalt magyar könyvelő szerepkör
SYSTEM_PROMPT = """Te egy tapasztalt magyar könyvelő és pénzügyi ellenőr vagy.
Kapsz egy számlából kinyert strukturált adatot és az eredeti számla szövegét.

Feladataid:
1. Egészítsd ki a hiányzó mezőket, ha a szövegből kiolvasható
2. Ellenőrizd az ÁFA számítás helyességét (nettó × ÁFA kulcs = ÁFA összeg)
3. Ellenőrizd a dátumokat (fizetési határidő >= számla kelte)
4. Keresd a duplikáció gyanúját, szokatlan összegeket
5. Ha az eladó adószáma hiányzik, az HIBA (nem figyelmeztetés)
6. Írj egy rövid (3-5 mondat) könyvelői értékelést magyarul

Válaszolj kizárólag JSON formátumban az alábbi sémának megfelelően:
{
  "filled_fields": { "mezőnév": "érték" },
  "issues": [
    {
      "field": "mezőnév",
      "severity": "ok|warning|error",
      "message": "Magyar nyelvű leírás",
      "suggestion": "Javítási javaslat"
    }
  ],
  "summary": "Magyar könyvelői szöveges értékelés..."
}"""


class GeminiValidationResult:
    """A Gemini API válaszának feldolgozott eredménye."""

    def __init__(self, filled_fields: dict, issues: list[ValidationIssue], summary: str):
        self.filled_fields = filled_fields      # Pótolt mezők szótára
        self.issues = issues                    # Validációs problémák listája
        self.summary = summary                  # Könyvelői összefoglaló szöveg


def _configure_gemini():
    """Gemini API kliens konfigurálása az API kulccsal."""
    genai.configure(api_key=settings.gemini_api_key)


def _parse_gemini_response(response_text: str) -> tuple[dict, list[ValidationIssue], str]:
    """
    Gemini JSON válasz feldolgozása.
    Visszaadja a pótolt mezőket, validációs hibákat és az összefoglalót.
    """
    # JSON blokk kinyerése, ha markdown kód blokkban van
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    data = json.loads(text)

    filled_fields = data.get("filled_fields", {})
    summary = data.get("summary", "")

    # Issues feldolgozása ValidationIssue modellekké
    issues = []
    for issue_data in data.get("issues", []):
        try:
            issues.append(ValidationIssue(
                field=issue_data.get("field"),
                severity=InvoiceStatus(issue_data.get("severity", "warning")),
                message=issue_data.get("message", ""),
                suggestion=issue_data.get("suggestion"),
            ))
        except (ValueError, KeyError) as e:
            logger.warning(f"Érvénytelen issue adat a Gemini válaszban: {e}")

    return filled_fields, issues, summary


async def validate_invoice(
    invoice_data: InvoiceData,
    raw_text: str = "",
    retry_count: int = 2,
) -> GeminiValidationResult:
    """
    Számla validálása és kiegészítése a Gemini API segítségével.

    Args:
        invoice_data: A Document AI által kinyert számlaadatok
        raw_text: Az eredeti számla szöveges tartalma (ha elérhető)
        retry_count: Próbálkozások száma timeout esetén

    Returns:
        GeminiValidationResult: Pótolt mezők, validációs hibák és összefoglaló
    """
    _configure_gemini()
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=SYSTEM_PROMPT,
    )

    # Prompt összeállítása – számlaadat JSON + nyers szöveg
    invoice_json = invoice_data.model_dump_json(indent=2)
    user_prompt = f"""Feldolgozandó számlaadatok (JSON):
{invoice_json}

Eredeti számla szövege:
{raw_text if raw_text else "(nem elérhető)"}

Kérlek, ellenőrizd és egészítsd ki a fenti adatokat!"""

    # API hívás retry logikával
    last_error = None
    for attempt in range(retry_count + 1):
        try:
            logger.info(f"Gemini validáció indítva (kísérlet: {attempt + 1})")
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,    # Alacsony hőmérséklet a konzisztens JSON válaszért
                ),
            )

            filled_fields, issues, summary = _parse_gemini_response(response.text)
            logger.info("Gemini validáció sikeres")
            return GeminiValidationResult(filled_fields, issues, summary)

        except Exception as e:
            last_error = e
            logger.warning(f"Gemini API hiba (kísérlet {attempt + 1}): {e}")

    # Összes próbálkozás sikertelen – hiba visszajelzés
    logger.error(f"Gemini API végleg sikertelen: {last_error}")
    error_issue = ValidationIssue(
        field=None,
        severity=InvoiceStatus.ERROR,
        message="A Gemini API validáció nem volt elérhető. Kézi ellenőrzés szükséges.",
        suggestion="Ellenőrizze az API kulcsot és a hálózati kapcsolatot.",
    )
    return GeminiValidationResult({}, [error_issue], "Automatikus értékelés nem elérhető.")
