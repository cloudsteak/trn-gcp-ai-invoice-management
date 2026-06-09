# Alkalmazás konfigurációs beállítások – minden érték környezeti változóból olvasódik
# Cloud Run Console-on bármikor módosítható: Service → Edit & Deploy → Variables & Secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Google Cloud Platform (kötelező – Cloud Run env vars vagy Secret Manager) ---
    gcp_project_id: str
    gcp_location: str = "eu"
    gcp_processor_id: str

    # --- Gemini API (kötelező – Secret Manager-ből érkezik) ---
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite"

    # --- Fájlkezelés (módosítható a GCP Console-on, vesszővel elválasztott string) ---
    max_file_size_mb: int = 20
    allowed_extensions: str = "pdf,jpg,jpeg,png"
    max_files_per_batch: int = 10
    upload_dir: str = "/tmp/invoices"

    # --- Szerver (Cloud Run ezeket automatikusan kezeli, vesszővel elválasztott string) ---
    port: int = 8000
    cors_origins: str = "*"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    def get_allowed_extensions(self) -> list[str]:
        return [e.strip() for e in self.allowed_extensions.split(",")]

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


# Globális példány – minden modulból importálható
settings = Settings()
