"""
Application Configuration
Environment-based settings using Pydantic Settings
Loads from environment variables first, then falls back to .env file
"""
import os
import json
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


def parse_cors_origins(value: str) -> list[str]:
    """Parse CORS origins from string (JSON array or comma-separated)"""
    if value.startswith("["):
        # JSON array format
        return json.loads(value)
    # Comma-separated format
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "CMDB API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database - required, no hardcoded defaults
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis - required, no hardcoded defaults
    REDIS_URL: str
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 2.0

    # JWT - required for security, no hardcoded defaults
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Encryption - required for credential storage, no hardcoded defaults
    ENCRYPTION_KEY: str

    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 32
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    PASSWORD_HISTORY_COUNT: int = 3

    # MFA
    OTP_ISSUER_NAME: str = "CMDB"

    # CORS - parse from env or .env
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

     # Upload
    UPLOAD_DIR: str = "/opt/upload/"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra fields in .env
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse CORS origins if it's a string from .env
        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            self.CORS_ORIGINS = parse_cors_origins(cors_env)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()