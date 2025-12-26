from typing import Literal, Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

from app.models_structure import GHTContext
from app.models_shared import SystemEndpoint, MessageLog

class MLLPConfig(SQLModel, table=True):
    """Configuration MLLP spécifique à un endpoint"""
    __table_args__ = {'extend_existing': True}  # Allow redefinition

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    port: int = Field(...)
    is_enabled: bool = Field(default=True)
    
    # Connection settings
    host: str = Field(default="0.0.0.0")    # Default: listen on all interfaces
    sending_app: str                         # MSH-3
    sending_facility: str                    # MSH-4
    receiving_app: Optional[str] = None      # MSH-5
    receiving_facility: Optional[str] = None # MSH-6
    
    # Advanced settings
    buffer_size: int = Field(default=4096)  # Read buffer size
    send_ack: bool = Field(default=True)    # Whether to send ACKs
    timeout: float = Field(default=30.0)    # Socket timeout in seconds
    
    # Timing fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Owner relationship
    endpoint_id: int = Field(foreign_key="systemendpoint.id")
    endpoint: SystemEndpoint = Relationship(back_populates="mllp_configs")

class FHIRConfig(SQLModel, table=True):
    """Configuration FHIR spécifique à un endpoint"""
    __table_args__ = {'extend_existing': True}  # Allow redefinition
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)            # Name (e.g., "Patients", "Encounters")
    base_url: str = Field(...)               # Base URL for this FHIR endpoint
    path_prefix: str = ""                    # Optional path prefix (e.g., "/adt")
    version: str = "R4"                      # FHIR version

    # Auth settings
    auth_kind: str = Field(default="none")  # "none" or "bearer"
    auth_token: Optional[str] = None         # Bearer token if needed
    
    # Resource settings
    supported_resources: str = "*"           # Resource list ("*" = all)
    is_enabled: bool = Field(default=True)
    
    # Connection settings
    verify_ssl: bool = Field(default=True)   # Whether to verify SSL certs
    timeout: float = Field(default=30.0)     # Request timeout in seconds
    
    # Timing fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Owner relationship
    endpoint_id: int = Field(foreign_key="systemendpoint.id")
    endpoint: SystemEndpoint = Relationship(back_populates="fhir_configs")

class FTPConfig(SQLModel, table=True):
    """Configuration FTP/SFTP spécifique à un endpoint"""
    __table_args__ = {'extend_existing': True}  # Allow redefinition

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    is_enabled: bool = Field(default=True)

    # Connection settings
    host: str = Field(...)                    # FTP/SFTP server hostname
    port: int = Field(default=21)             # Port (21 for FTP, 22 for SFTP)
    username: str = Field(...)                # Username for authentication
    password: str = Field(...)                # Password for authentication
    use_sftp: bool = Field(default=False)     # True for SFTP, False for FTP

    # Directory settings
    remote_inbox_path: str = Field(default="/")    # Remote directory to read from
    remote_outbox_path: str = Field(default="/")   # Remote directory to write to
    remote_archive_path: str = Field(default="/archive")  # Remote archive directory
    remote_error_path: str = Field(default="/error")      # Remote error directory

    # Local directories (for processing)
    local_inbox_path: Optional[str] = None    # Local directory for incoming files
    local_outbox_path: Optional[str] = None   # Local directory for outgoing files
    local_archive_path: Optional[str] = None  # Local archive directory
    local_error_path: Optional[str] = None    # Local error directory

    # File settings
    file_extensions: str = Field(default=".hl7,.txt,.json")  # Supported file extensions
    file_pattern: Optional[str] = None        # File name pattern (regex)
    delete_after_process: bool = Field(default=False)  # Delete remote files after processing

    # Transfer settings
    passive_mode: bool = Field(default=True)  # FTP passive mode
    timeout: float = Field(default=30.0)      # Connection timeout in seconds
    retry_count: int = Field(default=3)       # Number of retry attempts
    retry_delay: float = Field(default=5.0)   # Delay between retries in seconds

    # Security settings (for SFTP)
    key_file_path: Optional[str] = None       # Path to private key file
    key_passphrase: Optional[str] = None      # Passphrase for private key
    host_key_policy: str = Field(default="auto-add")  # Host key policy: auto-add, reject-new, ignore

    # Timing fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Owner relationship
    endpoint_id: int = Field(foreign_key="systemendpoint.id")
    endpoint: SystemEndpoint = Relationship(back_populates="ftp_configs")

# MessageLog moved to models_shared.py
