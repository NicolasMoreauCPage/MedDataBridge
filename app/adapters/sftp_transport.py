import paramiko
import stat
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class SFTPReader:
    """
    Reads files from a remote SFTP directory.
    """
    def __init__(
        self,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
        password: Optional[str] = None,
        remote_path: str = ".",
        extensions: Optional[List[str]] = None,
        archive_path: Optional[str] = None,
        error_path: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.extensions = extensions or []
        self.archive_path = archive_path
        self.error_path = error_path
        self.transport = None
        self.sftp = None

    def connect(self):
        logger.info(f"Connecting to SFTP {self.host}:{self.port} as {self.username}")
        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(username=self.username, password=self.password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        logger.info("SFTP connection established")

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()
        logger.info("SFTP connection closed")

    def list_pending_files(self) -> List[str]:
        files = []
        for entry in self.sftp.listdir_attr(self.remote_path):
            if not stat.S_ISREG(entry.st_mode):
                continue
            if self.extensions and not any(entry.filename.lower().endswith(ext) for ext in self.extensions):
                continue
            files.append(entry.filename)
        return sorted(files)

    def read_file(self, filename: str) -> str:
        remote_file = f"{self.remote_path}/{filename}"
        with self.sftp.open(remote_file, 'r') as f:
            content = f.read()
        # SFTP peut renvoyer bytes selon le mode, forcer str
        if isinstance(content, bytes):
            try:
                return content.decode('utf-8')
            except Exception:
                return content.decode('latin-1')
        return content

    def move_file(self, filename: str, dest_dir: str):
        src = f"{self.remote_path}/{filename}"
        dst = f"{dest_dir}/{filename}"
        self.sftp.rename(src, dst)

    def remove_file(self, filename: str):
        self.sftp.remove(f"{self.remote_path}/{filename}")
