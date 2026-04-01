from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- MongoDB Connection ---
    MONGODB_URL: str
    DATABASE_NAME: str
    HR_DATABASE_NAME: str

    # --- Security & Auth ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOW_PASSWORDLESS_LOGIN: bool = False  # Dev-only fallback; keep False in production.
    DISABLE_AUTH: bool = False  # Dev-only: bypass JWT/RBAC checks entirely.

    # Values from legacy HR `Employees.role` that should be treated as payroll-admins.
    # Override via env with JSON, e.g.: HR_ADMIN_ROLES=["HR Admin","Admin"]
    HR_ADMIN_ROLES: list[str] = ["HR Admin"]

    # --- CORS ---
    # For local dev, React/Vite typically runs on 5173.
    # You can override via env with JSON, e.g.:
    # CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- HR Sync ---
    AUTO_SYNC_HR: bool = False
    AUTO_SYNC_INTERVAL_MINUTES: int = 15

    # --- Pydantic Settings Configuration ---
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Create a singleton instance for the entire application
settings = Settings()
