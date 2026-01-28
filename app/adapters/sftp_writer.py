import paramiko
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SFTPWriter:
    """
    Writes files to a remote SFTP directory.
    """
    def __init__(
        self,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
        password: Optional[str] = None,
        remote_path: str = ".",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.transport = None
        self.sftp = None

    def connect(self):
        logger.info(f"[SFTPWriter] Connecting to SFTP {self.host}:{self.port} as {self.username}")
        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(username=self.username, password=self.password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        logger.info("[SFTPWriter] SFTP connection established")

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()
        logger.info("[SFTPWriter] SFTP connection closed")

    def write_file(self, filename: str, content: str, encoding: str = "utf-8"):
        remote_file = f"{self.remote_path}/{filename}"
        with self.sftp.open(remote_file, 'w') as f:
            f.write(content.encode(encoding) if isinstance(content, str) else content)
        logger.info(f"[SFTPWriter] File written: {remote_file}")
