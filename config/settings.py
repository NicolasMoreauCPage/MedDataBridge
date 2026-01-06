"""
Application settings and configuration
"""
import os
from typing import Optional


class Settings:
    """Application settings"""
    
    # Application info
    app_name: str = "MedDataBridge"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    testing: bool = os.getenv("TESTING", "false").lower() == "true"
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./medbridge.db")
    db_echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # File polling
    file_poll_interval: int = int(os.getenv("FILE_POLL_INTERVAL", "60"))


# Global settings instance
settings = Settings()
