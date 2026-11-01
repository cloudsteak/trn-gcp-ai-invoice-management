# CSAK AZ API-NÉZET MIATT – ez az egész fájl.
# Egy számla feldolgozása közben összegyűjti a Document AI és Gemini hívások
# oktatási másolatát. A kinyert számlaadatot és a validációt nem befolyásolja.
from contextvars import ContextVar, Token
from datetime import datetime, timezone

from models.result import ApiCallTrace
from utils.logger import get_logger

logger = get_logger(__name__)

_bucket: ContextVar[list[ApiCallTrace] | None] = ContextVar("api_call_traces", default=None)


def begin_api_traces() -> Token:
    """Új, üres hívásnapló a jelenlegi feladathoz."""
    return _bucket.set([])


def snapshot_api_traces() -> list[ApiCallTrace]:
    """Az eddig rögzített hívások másolata."""
    return list(_bucket.get() or [])


def reset_api_traces(token: Token) -> None:
    """Napló visszaállítása a feladat végén."""
    _bucket.reset(token)


def clip_text(text: str | None, limit: int = 4000) -> str:
    """Hosszú prompt / OCR szöveg vágása, hogy a felület olvasható maradjon."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… ({len(text)} karakterből az első {limit} látható)"


def _layer_for_service(service: str) -> str:
    """Document AI és a nyelvi modell külön réteg a panelen."""
    if "document" in service.lower():
        return "docai"
    return "ai"


def record_api_call(
    *,
    service: str,
    operation: str,
    status: str,
    duration_ms: int,
    request: dict,
    response: dict | None = None,
    error: str | None = None,
) -> None:
    """Egy Document AI vagy Gemini hívás hozzáadása a naplóhoz. Hiba nem állítja meg a feldolgozást."""
    try:
        bucket = _bucket.get()
        if bucket is None:
            return
        bucket.append(
            ApiCallTrace(
                direction="be-ai",
                layer=_layer_for_service(service),
                service=service,
                operation=operation,
                status=status,
                duration_ms=max(0, int(duration_ms)),
                occurred_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                request=request,
                response=response,
                error=error,
            )
        )
    except Exception as exc:
        logger.warning(f"API nyom rögzítése sikertelen: {exc}")


def annotate_last_trace(service: str, extra: dict) -> None:
    """Az utolsó sikeres hívás válaszához hozzáírja a backend által értelmezett kimenetet."""
    try:
        bucket = _bucket.get()
        if not bucket:
            return
        for trace in reversed(bucket):
            if trace.service == service and trace.status == "ok":
                response = dict(trace.response or {})
                response.update(extra)
                trace.response = response
                return
    except Exception as exc:
        logger.warning(f"API nyom kiegészítése sikertelen: {exc}")
