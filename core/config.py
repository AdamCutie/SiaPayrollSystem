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

    # --- Pydantic Settings Configuration ---
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Create a singleton instance for the entire application
settings = Settings()
