# Gemini API integráció – számlaadat validáció, kiegészítés és könyvelői értékelés
# Vertex AI + ADC (Application Default Credentials) – nincs szükség GEMINI_API_KEY-re
import asyncio
import json
from typing import Optional

from google import genai
from google.genai import types

from config import settings
from models.invoice import InvoiceData
from models.result import ValidationIssue, InvoiceStatus
from utils.logger import get_logger

logger = get_logger(__name__)

_genai_client: Optional[genai.Client] = None

# Gemini system prompt – tapasztalt magyar könyvelő szerepkör
SYSTEM_PROMPT = """Te egy tapasztalt magyar könyvelő és pénzügyi ellenőr vagy.
Kapsz egy számlából kinyert strukturált adatot és az eredeti számla szövegét.

Feladataid:
1. Egészítsd ki a hiányzó mezőket a JSON-ban és az eredeti számlaszövegből (filled_fields)
2. Ellenőrizd az ÁFA számítás helyességét (nettó × ÁFA kulcs ≈ ÁFA összeg; nettó + ÁFA ≈ bruttó)
3. Ellenőrizd, hogy a „Fizetendő” mező megegyezik-e a „Bruttó összesen” értékével – eltérés FIGYELMEZTETÉS
4. Ellenőrizd a dátumokat (fizetési határidő >= számla kelte)
5. Keresd a valódi anomáliákat – ne jelezz hibát olyan mezőre, ami már szerepel a JSON-ban vagy a szövegből pótoltad
6. Az eladó adószáma (supplier_tax_id) hiánya csak akkor HIBA, ha se a JSON-ban, se a szövegből nem olvasható ki
7. A teljesítés dátuma (completion_date) hiánya FIGYELMEZTETÉS – nem Document AI hiba, könyvelési szempontból ellenőrizendő
8. Írj egy rövid (3-5 mondat) könyvelői értékelést magyarul

Fontos szabályok az issues listához:
- Ne jelents hiányzó mezőt (error), ha az adott mező már kitöltött a bemeneti JSON-ban
- Ha a filled_fields-ben pótoltad a mezőt, ne listázd hiányzóként az issues-ben
- A tételsoroknál csak akkor adj warningot, ha valóban ellentmondás van az összegekben
- Magyar számlán az adószám formátuma: 12345678-1-23

A filled_fields objektumba CSAK ténylegesen kiolvasott értékeket tegyél.
Hiányzó mezőt ne adj meg, és ne használj „HIÁNYZIK”, „N/A” vagy hasonló placeholder szöveget.

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
        self.filled_fields = filled_fields
        self.issues = issues
        self.summary = summary


def _get_genai_client() -> genai.Client:
    """Gemini kliens ADC-vel – helyben: gcloud auth application-default login."""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_location,
        )
    return _genai_client


def _parse_gemini_response(response_text: str) -> tuple[dict, list[ValidationIssue], str]:
    """Gemini JSON válasz feldolgozása."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    data = json.loads(text)

    filled_fields = data.get("filled_fields", {})
    summary = data.get("summary", "")

    issues = []
    for issue_data in data.get("issues", []):
        try:
            issues.append(
                ValidationIssue(
                    field=issue_data.get("field"),
                    severity=InvoiceStatus(issue_data.get("severity", "warning")),
                    message=issue_data.get("message", ""),
                    suggestion=issue_data.get("suggestion"),
                )
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Érvénytelen issue adat a Gemini válaszban: {e}")

    return filled_fields, issues, summary


async def _call_gemini_api(client: genai.Client, user_prompt: str) -> str:
    """Gemini hívás külön szálban – ne blokkolja az event loopot."""
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    if not response.text:
        raise ValueError("A Gemini üres választ adott vissza")
    return response.text


async def validate_invoice(
    invoice_data: InvoiceData,
    raw_text: str = "",
    retry_count: int = 2,
) -> GeminiValidationResult:
    """
    Számla validálása és kiegészítése a Gemini API segítségével (Vertex AI, ADC).
    """
    client = _get_genai_client()

    invoice_json = invoice_data.model_dump_json(indent=2)
    # OCR szöveg limit – elég a Gemini kontextusához, de ne lépje túl a tokent
    text_excerpt = raw_text[:30000] if raw_text else "(nem elérhető)"
    user_prompt = f"""Feldolgozandó számlaadatok (Document AI JSON – ezt ellenőrizd és egészítsd ki):
{invoice_json}

Eredeti számla szövege (OCR):
{text_excerpt}

Kérlek, ellenőrizd és egészítsd ki a fenti adatokat! A már kitöltött mezőket ne jelentsd hiányzónak."""

    last_error = None
    for attempt in range(retry_count + 1):
        try:
            logger.info(f"Gemini validáció indítva (kísérlet: {attempt + 1})")
            response_text = await _call_gemini_api(client, user_prompt)
            filled_fields, issues, summary = _parse_gemini_response(response_text)
            logger.info("Gemini validáció sikeres")
            return GeminiValidationResult(filled_fields, issues, summary)

        except Exception as e:
            last_error = e
            logger.warning(f"Gemini API hiba (kísérlet {attempt + 1}): {e}")

    logger.error(f"Gemini API végleg sikertelen: {last_error}")
    error_issue = ValidationIssue(
        field=None,
        severity=InvoiceStatus.ERROR,
        message="A Gemini API validáció nem volt elérhető. Kézi ellenőrzés szükséges.",
        suggestion="Ellenőrizze az ADC bejelentkezést (gcloud auth application-default login) és a roles/aiplatform.user jogosultságot.",
    )
    return GeminiValidationResult({}, [error_issue], "Automatikus értékelés nem elérhető.")
