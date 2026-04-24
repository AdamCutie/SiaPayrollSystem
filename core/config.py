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
    ALLOW_PASSWORDLESS_LOGIN: bool = False
    DISABLE_AUTH: bool = False  # If this is True in your .env, the system will return 'dev@local' and cause 401s in some UI parts.

    # Values from legacy HR `Employees.role` that should be treated as payroll-admins.
    # Override via env with JSON, e.g.: HR_ADMIN_ROLES=["HR Admin","Admin"]
    HR_ADMIN_ROLES: list[str] = [
        "HR Admin", 
        "HR Manager", 
        "HR Generalist", 
        "Recruitment Specialist", 
        "Payroll Manager", 
        "Payroll Specialist"
    ]

    # --- CORS ---
    # For local dev, React/Vite typically runs on 5173.
    # You can override via env with JSON, e.g.:
    # CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- HR Sync ---
    AUTO_SYNC_HR: bool = False
    AUTO_SYNC_INTERVAL_MINUTES: int = 15

    # --- Payslip Email Delivery ---
    PAYSLIP_EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "SIA Payroll System"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    # --- Pydantic Settings Configuration ---
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Create a singleton instance for the entire application
settings = Settings()
