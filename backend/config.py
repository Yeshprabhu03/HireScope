from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = "placeholder"
    OPENAI_API_KEY: str = "placeholder"
    GEMINI_API_KEY: str = "placeholder"
    HIRESCOPE_API_KEY: str = "hirescope_dev_secret"  # Default for local development
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Paths are absolute to work regardless of where the app is started
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR.parent / "data"

    DATABASE_URL: str = "sqlite:///./hirescope.db"
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "chroma_db")
    CHROMA_COLLECTION_NAME: str = "interview_experiences"
    DOL_H1B_DATA_PATH: str = str(DATA_DIR / "h1b_data.csv")
    GLASSDOOR_CACHE_DIR: str = str(DATA_DIR / "interview_corpus")
    USE_MOCK_DATA: bool = False

    class Config:
        # Look for .env in both backend/ and project root
        env_file = ("../.env", ".env")


settings = Settings()
