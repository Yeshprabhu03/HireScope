from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = "placeholder"
    OPENAI_API_KEY: str = "placeholder"
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "sqlite:///./hirescope.db"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "interview_experiences"
    DOL_H1B_DATA_PATH: str = "../data/h1b_data.csv"
    GLASSDOOR_CACHE_DIR: str = "../data/interview_corpus"
    USE_MOCK_DATA: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
