"""Application configuration loaded from environment variables."""

import os
from pathlib import Path


class Settings:
    """Application settings read from environment variables with defaults."""

    # --- Server ---
    APP_NAME: str = "AlphaFold3 Inference API"
    APP_VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8015"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Aliases for compatibility
    API_HOST: str = HOST
    API_PORT: int = PORT

    # --- Database ---
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/app/data/alphafold3.db")

    # --- Storage ---
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "/app/storage")

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "/app/logs/app.log")
    LOG_ROTATION: str = os.getenv("LOG_ROTATION", "7 days")
    LOG_RETENTION: str = os.getenv("LOG_RETENTION", "30 days")

    # --- AlphaFold Model ---
    ALPHAFOLD_DIR: str = os.getenv("ALPHAFOLD_DIR", "/app/alphafold")
    MODEL_DIR: str = os.getenv("MODEL_DIR", "/root/models")
    DB_DIR: str = os.getenv("DB_DIR", "/root/public_databases")
    INPUT_DIR: str = os.getenv("INPUT_DIR", "/app/storage/inputs")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/app/storage/outputs")

    # --- Business ---
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "30"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    @property
    def upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_BYTES

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.DATABASE_PATH}"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        Path(self.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(self.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
