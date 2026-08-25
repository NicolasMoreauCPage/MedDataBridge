"""
Application settings and configuration
"""
import os
from typing import Optional


def _env_flag(name: str, default: str = "false") -> bool:
    """Parse the conventional forms used for boolean environment variables."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Application settings"""
    
    # Application info
    app_name: str = "IntegraSanté by CPage"
    app_version: str = "1.1.0"
    debug: bool = _env_flag("DEBUG")
    testing: bool = _env_flag("TESTING")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/medbridge.db")
    db_echo: bool = _env_flag("DB_ECHO")
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # File polling
    file_poll_interval: int = int(os.getenv("FILE_POLL_INTERVAL", "60"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

    # Task concurrency (default used in tests and runtime if not configured)
    max_concurrent_tasks: int = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
    # Task manager defaults
    task_timeout: int = int(os.getenv("TASK_TIMEOUT", "3600"))
    task_worker_count: int = int(os.getenv("TASK_WORKER_COUNT", "3"))


# Global settings instance
settings = Settings()
