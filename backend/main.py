# FastAPI alkalmazás belépési pontja – routerek és middleware regisztrálása
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import upload, process, export


# FastAPI alkalmazás példány létrehozása
app = FastAPI(
    title="Intelligens Számlafeldolgozó API",
    description="Google Cloud Document AI + Gemini alapú számla feldolgozó rendszer",
    version="1.0.0",
)

# CORS middleware – vesszővel elválasztott string listává alakítva (pl. "https://a.com,https://b.com" vagy "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routerek regisztrálása
app.include_router(upload.router, prefix="/api", tags=["Feltöltés"])
app.include_router(process.router, prefix="/api", tags=["Feldolgozás"])
app.include_router(export.router, prefix="/api", tags=["Export"])


@app.get("/health")
async def health_check():
    """Állapot ellenőrző végpont – Cloud Run health check-hez"""
    return {"status": "ok"}
