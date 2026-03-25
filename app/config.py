from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # External APIs
    GOOGLE_MAPS_API_KEY: str = ""
    OSRM_BASE_URL: str = "http://localhost:5000"

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
